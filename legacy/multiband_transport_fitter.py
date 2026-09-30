#!/usr/bin/env python3
"""General multiband magnetotransport fitter for SDD-oriented workflows."""
from __future__ import annotations

import argparse, json, math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

E_CHARGE = 1.602176634e-19

@dataclass
class CarrierSpec:
    name: str
    kind: str
    n_init: float
    n_min: float
    n_max: float
    mu_init: float
    mu_min: float
    mu_max: float
    smooth_n: bool = True
    smooth_mu: bool = True
    monotonic_n: str = "none"
    monotonic_mu: str = "none"

    @property
    def sign(self) -> float:
        k = self.kind.lower()
        if k == "electron": return -1.0
        if k == "hole": return +1.0
        raise ValueError(f"Unknown carrier kind: {self.kind}")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_carriers(cfg: dict) -> List[CarrierSpec]:
    out=[]
    for c in cfg["carriers"]:
        out.append(CarrierSpec(
            name=c["name"], kind=c["kind"],
            n_init=float(c["density"]["init"]),
            n_min=float(c["density"]["min"]),
            n_max=float(c["density"]["max"]),
            mu_init=float(c["mobility"]["init"]),
            mu_min=float(c["mobility"]["min"]),
            mu_max=float(c["mobility"]["max"]),
            smooth_n=bool(c.get("smooth_density", True)),
            smooth_mu=bool(c.get("smooth_mobility", True)),
            monotonic_n=c.get("monotonic_density", "none").lower(),
            monotonic_mu=c.get("monotonic_mobility", "none").lower(),
        ))
    return out


def load_data(csv_path: str, cfg: dict) -> pd.DataFrame:
    cols=cfg["columns"]
    df=pd.read_csv(csv_path).copy()
    required=[cols["T"],cols["B"],cols["rhoxx"],cols["rhoxy"]]
    missing=[c for c in required if c not in df.columns]
    if missing: raise ValueError(f"Missing required columns: {missing}")
    df=df.rename(columns={cols["T"]:"T",cols["B"]:"B",cols["rhoxx"]:"rhoxx",cols["rhoxy"]:"rhoxy"})
    df=df[["T","B","rhoxx","rhoxy"]].dropna().astype(float)
    prep=cfg.get("preprocess",{})
    df["rhoxy"] *= float(prep.get("rhoxy_scale",1.0))

    if prep.get("symmetrize_rhoxx",False) or prep.get("antisymmetrize_rhoxy",False):
        groups=[]
        for T,g in df.groupby("T"):
            g=g.sort_values("B").reset_index(drop=True)
            xxmap={round(float(b),12):float(v) for b,v in zip(g.B,g.rhoxx)}
            xymap={round(float(b),12):float(v) for b,v in zip(g.B,g.rhoxy)}
            rows=[]
            for _,r in g.iterrows():
                b=float(r.B); xx=float(r.rhoxx); xy=float(r.rhoxy); k=round(-b,12)
                if prep.get("symmetrize_rhoxx",False) and k in xxmap: xx=0.5*(xx+xxmap[k])
                if prep.get("antisymmetrize_rhoxy",False) and k in xymap: xy=0.5*(xy-xymap[k])
                rows.append((T,b,xx,xy))
            groups.append(pd.DataFrame(rows,columns=["T","B","rhoxx","rhoxy"]))
        df=pd.concat(groups,ignore_index=True)
    return df.sort_values(["T","B"]).reset_index(drop=True)


def conductivity_model(B_T, n_cm3, mu_cm2Vs, signs, hall_polarity=1.0):
    B=np.asarray(B_T,float)
    n=np.asarray(n_cm3,float)*1e6
    mu=np.asarray(mu_cm2Vs,float)*1e-4
    s=np.asarray(signs,float)
    muB=mu[:,None]*B[None,:]
    den=1.0+muB**2
    sxx=np.sum(n[:,None]*E_CHARGE*mu[:,None]/den,axis=0)
    sxy=np.sum(hall_polarity*s[:,None]*n[:,None]*E_CHARGE*(mu[:,None]**2)*B[None,:]/den,axis=0)
    return sxx,sxy


def resistivity_from_conductivity(sxx,sxy):
    den=sxx**2+sxy**2
    return (sxx/den)*1e8, (-sxy/den)*1e8


def conductivity_from_resistivity(rhoxx_uohmcm,rhoxy_uohmcm):
    rxx=np.asarray(rhoxx_uohmcm,float)/1e8
    rxy=np.asarray(rhoxy_uohmcm,float)/1e8
    den=rxx**2+rxy**2
    return rxx/den, -rxy/den


def base_parameter_vector(carriers):
    p=[]
    for c in carriers: p += [c.n_init,c.mu_init]
    return np.asarray(p,float)


def parameter_bounds(carriers):
    lo=[]; hi=[]
    for c in carriers:
        lo += [c.n_min,c.mu_min]; hi += [c.n_max,c.mu_max]
    return np.asarray(lo,float),np.asarray(hi,float)


def decode_vector(p,carriers):
    p=np.asarray(p,float)
    return p[0::2],p[1::2],np.asarray([c.sign for c in carriers],float)


def log_encode(p):
    p=np.asarray(p,float)
    if np.any(p<=0): raise ValueError("All fitted parameters must be positive.")
    return np.log(p)


def log_decode(x): return np.exp(np.asarray(x,float))


def initial_override_for_temperature(T,carriers,cfg):
    overrides=cfg.get("initial_by_temperature",{})
    keys=[str(T), str(int(T)) if float(T).is_integer() else None]
    entry=None
    for k in keys:
        if k is not None and k in overrides: entry=overrides[k]; break
    if entry is None: return None
    p=base_parameter_vector(carriers)
    for i,c in enumerate(carriers):
        if c.name in entry:
            if "density" in entry[c.name]: p[2*i]=float(entry[c.name]["density"])
            if "mobility" in entry[c.name]: p[2*i+1]=float(entry[c.name]["mobility"])
    return p


def robust_scale(y):
    y=np.asarray(y,float); m=np.median(np.abs(y))
    if m>0: return float(m)
    s=np.std(y); return float(s if s>0 else 1.0)


def r_squared(y,yhat):
    y=np.asarray(y,float); yhat=np.asarray(yhat,float)
    ssr=np.sum((y-yhat)**2); sst=np.sum((y-np.mean(y))**2)
    return float(1-ssr/sst) if sst>0 else float("nan")


def predict_for_temperature(B,p,carriers,cfg):
    n,mu,signs=decode_vector(p,carriers)
    hp=float(cfg.get("model",{}).get("hall_polarity",1.0))
    sxx,sxy=conductivity_model(B,n,mu,signs,hp)
    rxx,rxy=resistivity_from_conductivity(sxx,sxy)
    return {"sigma_xx":sxx,"sigma_xy":sxy,"rhoxx":rxx,"rhoxy":rxy}


def data_targets(g,fit_space):
    if fit_space=="rho": return g.rhoxx.to_numpy(float),g.rhoxy.to_numpy(float)
    if fit_space=="sigma": return conductivity_from_resistivity(g.rhoxx.to_numpy(float),g.rhoxy.to_numpy(float))
    raise ValueError("fit_space must be rho or sigma")


def model_targets(pred,fit_space):
    if fit_space=="rho": return pred["rhoxx"],pred["rhoxy"]
    if fit_space=="sigma": return pred["sigma_xx"],pred["sigma_xy"]
    raise ValueError("fit_space must be rho or sigma")


def channel_residual(g,p,carriers,cfg):
    opt=cfg["optimization"]
    mode=opt.get("fit_mode","both").lower(); space=opt.get("fit_space","rho").lower()
    B=g.B.to_numpy(float); pred=predict_for_temperature(B,p,carriers,cfg)
    yx,yy=data_targets(g,space); mx,my=model_targets(pred,space)
    sx=robust_scale(yx); sy=robust_scale(yy)
    wx=float(opt.get("weight_rhoxx",1.0)); wy=float(opt.get("weight_rhoxy",1.0))
    lw=opt.get("low_field_weight",{})
    if lw.get("enabled",False):
        alpha=float(lw.get("alpha",0.0)); B0=float(lw.get("B0_T",1.0))
        low_w=1+alpha*np.exp(-(np.abs(B)/B0)**2)
    else: low_w=np.ones_like(B)
    parts=[]
    if mode in ("both","rhoxx"): parts.append(((mx-yx)/sx)*math.sqrt(wx)*np.sqrt(low_w))
    if mode in ("both","rhoxy"): parts.append(((my-yy)/sy)*math.sqrt(wy))
    if not parts: raise ValueError("fit_mode must be both, rhoxx, or rhoxy")
    return np.concatenate(parts)


def _smooth_mask(carriers,which):
    mask=[]
    for c in carriers:
        if which=="n": mask += [c.smooth_n,False]
        else: mask += [False,c.smooth_mu]
    return np.asarray(mask,bool)


def first_difference_smoothness(x_now,x_prev,carriers,cfg):
    sm=cfg.get("smoothing",{})
    if not sm.get("enabled",False): return np.array([],float)
    parts=[]
    mn=_smooth_mask(carriers,"n"); mm=_smooth_mask(carriers,"mu")
    ln=float(sm.get("lambda_density",0)); lm=float(sm.get("lambda_mobility",0))
    if ln>0 and np.any(mn): parts.append(math.sqrt(ln)*(x_now-x_prev)[mn])
    if lm>0 and np.any(mm): parts.append(math.sqrt(lm)*(x_now-x_prev)[mm])
    return np.concatenate(parts) if parts else np.array([],float)


def global_smoothness(X,T,carriers,cfg):
    sm=cfg.get("smoothing",{})
    if not sm.get("enabled",False): return np.array([],float)
    order=int(sm.get("order",2)); T=np.asarray(T,float)
    if len(T)<2: return np.array([],float)
    dtmed=float(np.median(np.diff(T)))
    parts=[]
    for mask,lam in [(_smooth_mask(carriers,"n"),float(sm.get("lambda_density",0))),(_smooth_mask(carriers,"mu"),float(sm.get("lambda_mobility",0)))]:
        if lam<=0 or not np.any(mask): continue
        Y=X[:,mask]
        if order==1:
            for i in range(1,len(T)):
                dt=max(T[i]-T[i-1],1e-12)
                parts.append(math.sqrt(lam)*math.sqrt(dtmed/dt)*(Y[i]-Y[i-1]))
        elif order==2:
            if len(T)<3: continue
            for i in range(1,len(T)-1):
                d1=max(T[i]-T[i-1],1e-12); d2=max(T[i+1]-T[i],1e-12)
                curvature=((Y[i+1]-Y[i])/d2-(Y[i]-Y[i-1])/d1)*dtmed
                parts.append(math.sqrt(lam)*curvature)
        else: raise ValueError("smoothing.order must be 1 or 2")
    return np.concatenate(parts) if parts else np.array([],float)


def monotonic_penalty_global(X,carriers,cfg):
    mono=cfg.get("monotonic_penalty",{})
    if not mono.get("enabled",False): return np.array([],float)
    lam=float(mono.get("lambda",10.0)); parts=[]
    for j,c in enumerate(carriers):
        for off,direction in [(0,c.monotonic_n),(1,c.monotonic_mu)]:
            if direction=="none": continue
            d=np.diff(X[:,2*j+off])
            if direction=="increase": v=np.minimum(d,0.0)
            elif direction=="decrease": v=np.maximum(d,0.0)
            else: raise ValueError(f"Bad monotonic direction: {direction}")
            parts.append(math.sqrt(lam)*v)
    return np.concatenate(parts) if parts else np.array([],float)


def solve_single_temperature(g,x0,log_lo,log_hi,carriers,cfg,x_prev=None):
    opt=cfg["optimization"]
    def residual(x):
        r=channel_residual(g,log_decode(x),carriers,cfg)
        if x_prev is not None:
            s=first_difference_smoothness(x,x_prev,carriers,cfg)
            if s.size: r=np.concatenate([r,s])
        return r
    best=None; rng=np.random.default_rng(int(opt.get("random_seed",12345)))
    for k in range(int(opt.get("multi_start",1))):
        start=np.clip(x0 if k==0 else x0+rng.normal(0,float(opt.get("multi_start_log_sigma",0.25)),x0.shape),log_lo+1e-12,log_hi-1e-12)
        res=least_squares(residual,start,bounds=(log_lo,log_hi),max_nfev=int(opt.get("max_nfev",30000)),ftol=float(opt.get("ftol",1e-10)),xtol=float(opt.get("xtol",1e-10)),gtol=float(opt.get("gtol",1e-10)),loss=opt.get("loss","linear"),f_scale=float(opt.get("f_scale",1.0)))
        if best is None or res.cost<best.cost: best=res
    return best.x


def fit_independent_or_sequential(df,carriers,cfg,strategy):
    p0=base_parameter_vector(carriers); lo,hi=parameter_bounds(carriers); llo,lhi=log_encode(lo),log_encode(hi)
    sol={}; prev=None
    for T in sorted(df["T"].unique()):
        g=df[df["T"]==T].copy(); override=initial_override_for_temperature(T,carriers,cfg)
        if override is not None: start=override
        elif strategy=="sequential" and prev is not None: start=log_decode(prev)
        else: start=p0
        x0=log_encode(np.clip(start,lo*(1+1e-12),hi*(1-1e-12)))
        x=solve_single_temperature(g,x0,llo,lhi,carriers,cfg,prev if strategy=="sequential" else None)
        sol[float(T)]=log_decode(x); prev=x
    return sol


def fit_global_smooth(df,carriers,cfg):
    opt=cfg["optimization"]; temps=np.asarray(sorted(df["T"].unique()),float); nT=len(temps)
    p0=base_parameter_vector(carriers); lo,hi=parameter_bounds(carriers); llo,lhi=log_encode(lo),log_encode(hi)
    X0=np.tile(log_encode(p0),(nT,1))
    for i,T in enumerate(temps):
        ov=initial_override_for_temperature(T,carriers,cfg)
        if ov is not None: X0[i]=log_encode(np.clip(ov,lo*(1+1e-12),hi*(1-1e-12)))
    x0=X0.ravel(); lower=np.tile(llo,nT); upper=np.tile(lhi,nT); groups={T:df[df["T"]==T].copy() for T in temps}
    def residual(flat):
        X=flat.reshape(nT,-1); parts=[]
        for i,T in enumerate(temps): parts.append(channel_residual(groups[T],log_decode(X[i]),carriers,cfg))
        s=global_smoothness(X,temps,carriers,cfg)
        if s.size: parts.append(s)
        m=monotonic_penalty_global(X,carriers,cfg)
        if m.size: parts.append(m)
        return np.concatenate(parts)
    best=None; rng=np.random.default_rng(int(opt.get("random_seed",12345)))
    for k in range(int(opt.get("multi_start",1))):
        start=np.clip(x0 if k==0 else x0+rng.normal(0,float(opt.get("multi_start_log_sigma",0.15)),x0.shape),lower+1e-12,upper-1e-12)
        res=least_squares(residual,start,bounds=(lower,upper),max_nfev=int(opt.get("max_nfev",50000)),ftol=float(opt.get("ftol",1e-9)),xtol=float(opt.get("xtol",1e-9)),gtol=float(opt.get("gtol",1e-9)),loss=opt.get("loss","linear"),f_scale=float(opt.get("f_scale",1.0)))
        if best is None or res.cost<best.cost: best=res
    X=best.x.reshape(nT,-1)
    return {float(T):log_decode(X[i]) for i,T in enumerate(temps)}


def build_outputs(df,solutions,carriers,cfg,out_dir):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    prows=[]; mrows=[]; make_plots=bool(cfg.get("output",{}).get("make_plots",True)); dpi=int(cfg.get("output",{}).get("plot_dpi",180))
    for T in sorted(solutions):
        p=solutions[T]; g=df[df["T"]==T].copy().sort_values("B"); B=g.B.to_numpy(float); pred=predict_for_temperature(B,p,carriers,cfg)
        dsxx,dsxy=conductivity_from_resistivity(g.rhoxx.to_numpy(float),g.rhoxy.to_numpy(float))
        pd.DataFrame({"T(K)":T,"B(T)":B,"rhoxx_data(microohm_cm)":g.rhoxx,"rhoxy_data(microohm_cm)":g.rhoxy,"rhoxx_fit(microohm_cm)":pred["rhoxx"],"rhoxy_fit(microohm_cm)":pred["rhoxy"],"sigma_xx_data(S_per_m)":dsxx,"sigma_xy_data(S_per_m)":dsxy,"sigma_xx_fit(S_per_m)":pred["sigma_xx"],"sigma_xy_fit(S_per_m)":pred["sigma_xy"],"residual_rhoxx(microohm_cm)":pred["rhoxx"]-g.rhoxx.to_numpy(float),"residual_rhoxy(microohm_cm)":pred["rhoxy"]-g.rhoxy.to_numpy(float)}).to_csv(out/f"{T:g}K_fit.csv",index=False)
        row={"T(K)":T}
        for i,c in enumerate(carriers): row[f"{c.name}_density(cm^-3)"]=p[2*i]; row[f"{c.name}_mobility(cm^2_Vs)"]=p[2*i+1]
        prows.append(row)
        rxx=g.rhoxx.to_numpy(float); rxy=g.rhoxy.to_numpy(float)
        mrows.append({"T(K)":T,"R2_rhoxx":r_squared(rxx,pred["rhoxx"]),"R2_rhoxy":r_squared(rxy,pred["rhoxy"]),"RMSE_rhoxx(microohm_cm)":float(np.sqrt(np.mean((rxx-pred["rhoxx"])**2))),"RMSE_rhoxy(microohm_cm)":float(np.sqrt(np.mean((rxy-pred["rhoxy"])**2)))})
        if make_plots and plt is not None:
            for key,label in [("rhoxx",r"$\rho_{xx}$ ($\mu\Omega$ cm)"),("rhoxy",r"$\rho_{xy}$ ($\mu\Omega$ cm)")]:
                plt.figure(); plt.plot(B,g[key],"o",ms=3,label="data"); plt.plot(B,pred[key],"-",lw=1.5,label="fit"); plt.xlabel("B (T)"); plt.ylabel(label); plt.legend(); plt.tight_layout(); plt.savefig(out/f"{T:g}K_{key}.png",dpi=dpi); plt.close()
    pd.DataFrame(prows).to_csv(out/"fit_parameters_vs_T.csv",index=False); pd.DataFrame(mrows).to_csv(out/"fit_metrics_vs_T.csv",index=False)
    with open(out/"resolved_config.json","w",encoding="utf-8") as f: json.dump(cfg,f,indent=2,ensure_ascii=False)


def main():
    ap=argparse.ArgumentParser(description="General multiband magnetotransport fitter")
    ap.add_argument("--data",required=True); ap.add_argument("--config",required=True); ap.add_argument("--out",required=True)
    args=ap.parse_args(); cfg=load_config(args.config); carriers=parse_carriers(cfg); df=load_data(args.data,cfg)
    strategy=cfg["optimization"].get("temperature_strategy","sequential").lower()
    if strategy in ("independent","sequential"): sol=fit_independent_or_sequential(df,carriers,cfg,strategy)
    elif strategy=="global_smooth": sol=fit_global_smooth(df,carriers,cfg)
    else: raise ValueError("temperature_strategy must be independent, sequential, or global_smooth")
    build_outputs(df,sol,carriers,cfg,args.out); print(f"Done. Results written to: {args.out}")

if __name__=="__main__": main()
