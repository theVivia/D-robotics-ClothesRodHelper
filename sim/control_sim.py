"""单模块位置控制仿真：阶跃响应、稳态误差、超调量。

被控对象（简化模型，参数都是**设计值/估算值**，不是实测）
------------------------------------------------------
* 运动质量 m = 1.6 kg（单元 0.6 kg + 湿衣物 1.0 kg），轮面线速度上限 60 mm/s。
* 驱动器内部速度环已整定好，按一阶等效：τ_v = 40 ms。
  即位置环给"速度指令"，实际速度以 40 ms 时间常数跟随。
* 阻力：库仑阻力等效加速度 150 mm/s²（夹爪压紧 + 轴承），用 tanh(v/1.5) 平滑；
  另加坡道扰动：晾衣杆/栏杆不水平 1° 时重力分量 171 mm/s²（估算）。
  这两项让**纯 P 控制必然有稳态误差**，只有积分项能消掉。
* 测量：磁编码器量化 0.1 mm + 高斯噪声 σ=0.15 mm；初始位置误差 −5 mm。
* 闭环延迟：10 ms（编码器→MCU→PWM，本地环）。另给一档 120 ms 的
  "PID 跑在中枢、经 MQTT 下发"的对照，用来说明**位置环必须跑在单元本地**。
* 忽略：静摩擦黏滑、轮子打滑、杆弯曲（都归 P1 风险项）。

控制律
------
    v_ref = clamp( kp·e + ki·∫e dt − kd·v_meas , ±v_max )，  e = 目标位置 − 编码器位置
默认带条件积分抗饱和（饱和时停积分，且 |ki·I| ≤ v_max）；
脚本里另跑一档 "无抗饱和" 作反面教材，用来说明代码里为什么要写抗饱和。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

# ---- 物理/驱动器参数（mm、s、mm/s²）----
DT = 0.002                 # 仿真步长 2 ms
T_END = 12.0               # 仿真时长
V_MAX = 60.0               # 轮面线速度上限（N20 60 rpm + 20 mm 轮）
TAU_V = 0.04               # 速度环一阶时间常数
A_DIST = -171.0            # 1° 坡道等效扰动加速度
A_FRIC = 150.0             # 库仑阻力等效加速度（幅值）
V_EPS = 1.5                # tanh 平滑速度尺度
QUANT_MM = 0.1             # 编码器量化
NOISE_SIGMA_MM = 0.15      # 编码器随机噪声
INIT_ERR_MM = -5.0         # 初始位置误差
TARGET_MM = 300.0          # 阶跃目标（mm）
SETTLE_BAND = 0.02         # 2% 稳定带
DELAY_S = 0.010            # 本地闭环延迟（编码器→MCU→PWM）
GRAVITY_MM_S2 = 9810.0     # 重力加速度


def tilt_to_disturbance(tilt_deg: float) -> float:
    """晾衣杆倾斜 tilt 度时，沿杆方向的重力分量（mm/s²，负 = 向下坡方向）。"""
    return -GRAVITY_MM_S2 * float(np.sin(np.radians(tilt_deg)))


@dataclass
class Gains:
    """一组位置环参数。"""

    name: str
    kp: float
    ki: float = 0.0
    kd: float = 0.0
    note: str = ""
    delay_s: Optional[float] = None      # None → 用模块默认 DELAY_S
    windup_guard: bool = True            # 是否启用抗饱和


@dataclass
class ControlResult:
    """一次仿真的轨迹与指标。"""

    t: np.ndarray                 # (T,) 时间 s
    x: np.ndarray                 # (T,) 位置 mm（批量时取均值）
    v: np.ndarray                 # (T,) 速度 mm/s
    v_ref: np.ndarray             # (T,) 速度指令 mm/s
    target: float
    metrics: Dict[str, float] = field(default_factory=dict)
    gains: Optional[Gains] = None
    x_all: Optional[np.ndarray] = None   # (T, n_runs) 每列一条轨迹


# ---------------------------------------------------------------------------
def _first_cross(t: np.ndarray, arr: np.ndarray, level: float) -> float:
    """arr 首次达到 level 的时刻（nan = 没达到）。"""
    mask = arr >= level
    idx = int(np.argmax(mask))
    return float(t[idx]) if mask[idx] else float("nan")


def simulate(gains: Gains,
             target: float = TARGET_MM,
             x0: float = INIT_ERR_MM,
             t_end: float = T_END,
             dt: float = DT,
             n_runs: int = 1,
             seed: int = 0,
             noise_sigma: float = NOISE_SIGMA_MM,
             quant: float = QUANT_MM,
             v_max: float = V_MAX,
             tau_v: float = TAU_V,
             a_dist: float = A_DIST,
             a_fric: float = A_FRIC,
             delay_s: Optional[float] = None) -> ControlResult:
    """仿真一次（或一批）位置阶跃。返回均值轨迹 + 指标（含逐列指标）。"""
    rng = np.random.default_rng(seed)
    x0_arr = np.broadcast_to(np.asarray(x0, dtype=float), (n_runs,)).copy()
    sig_arr = np.broadcast_to(np.asarray(noise_sigma, dtype=float), (n_runs,)).copy()
    vmax_arr = np.broadcast_to(np.asarray(v_max, dtype=float), (n_runs,)).copy()
    tau_arr = np.broadcast_to(np.asarray(tau_v, dtype=float), (n_runs,)).copy()
    dist_arr = np.broadcast_to(np.asarray(a_dist, dtype=float), (n_runs,)).copy()
    fric_arr = np.broadcast_to(np.asarray(a_fric, dtype=float), (n_runs,)).copy()
    delay = float(DELAY_S if delay_s is None else delay_s)
    nd = max(0, int(round(delay / dt)))
    steps = int(round(t_end / dt))
    t = np.arange(steps + 1) * dt

    x = x0_arr.copy()
    v = np.zeros(n_runs)
    integral = np.zeros(n_runs)
    meas_prev = x + rng.normal(0.0, sig_arr)
    v_filt = np.zeros(n_runs)

    X = np.zeros((steps + 1, n_runs))
    V = np.zeros((steps + 1, n_runs))
    VREF = np.zeros((steps + 1, n_runs))   # 指令历史（带延迟发布）
    X[0], V[0] = x, v

    i_max = np.full(n_runs, np.inf) if gains.ki <= 0 else vmax_arr / gains.ki
    for k in range(steps):
        meas = np.round((x + rng.normal(0.0, sig_arr)) / quant) * quant
        e = target - meas
        v_meas = (meas - meas_prev) / dt
        alpha = dt / (0.02 + dt)  # 20 ms 差分滤波
        v_filt += (v_meas - v_filt) * alpha
        meas_prev = meas

        u = gains.kp * e + gains.ki * integral - gains.kd * v_filt
        sat_hi = u > vmax_arr
        sat_lo = u < -vmax_arr
        cmd = np.clip(u, -vmax_arr, vmax_arr)

        if gains.windup_guard:
            can_int = ~((sat_hi & (e > 0)) | (sat_lo & (e < 0)))
            integral = np.where(can_int, integral + e * dt, integral)
            integral = np.clip(integral, -i_max, i_max)
        else:
            # 反面教材：饱和期照常积分，积分灌满（不夹紧）
            integral = integral + e * dt

        # 指令延迟 nd 步后生效
        if nd > 0:
            v_ref = VREF[k - nd] if k >= nd else np.zeros(n_runs)
        else:
            v_ref = cmd
        VREF[k + 1] = cmd

        dv = (v_ref - v) / tau_arr + dist_arr - fric_arr * np.tanh(v / V_EPS)
        v = v + dv * dt
        x = x + v * dt

        X[k + 1], V[k + 1] = x, v

    metrics = _metrics(t, X, target, x0_arr)
    return ControlResult(
        t=t,
        x=X.mean(axis=1),
        v=V.mean(axis=1),
        v_ref=VREF.mean(axis=1),
        target=float(target),
        metrics=metrics,
        gains=gains,
        x_all=X,
    )


def _metrics(t: np.ndarray, X: np.ndarray, target: float,
             x0: np.ndarray) -> Dict[str, float]:
    """由轨迹算指标（批量时返回均值 + 逐列数组）。"""
    n = X.shape[1]
    disp = target - x0
    band = SETTLE_BAND * abs(target)
    err = X - target

    overshoot = np.maximum(0.0, (X.max(axis=0) - target) / abs(target) * 100.0)
    overshoot_mm = np.maximum(0.0, X.max(axis=0) - target)
    peak = X.max(axis=0)
    rise = np.full(n, np.nan)
    settle = np.full(n, np.nan)
    for j in range(n):
        lvl10 = x0[j] + 0.1 * disp[j]
        lvl90 = x0[j] + 0.9 * disp[j]
        t10 = _first_cross(t, X[:, j], lvl10)
        t90 = _first_cross(t, X[:, j], lvl90)
        rise[j] = t90 - t10
        bad = np.abs(err[:, j]) > band
        if bad.any():
            last_bad = len(t) - 1 - int(np.argmax(bad[::-1]))
            settle[j] = t[min(last_bad + 1, len(t) - 1)]
        else:
            settle[j] = 0.0
    tail = slice(int(0.8 * len(t)), len(t))
    sse = err[tail].mean(axis=0)
    jitter = X[tail].std(axis=0)

    return {
        "overshoot_pct": float(overshoot.mean()),
        "overshoot_mm": float(overshoot_mm.mean()),
        "overshoot_max_pct": float(overshoot.max()),
        "peak_mm": float(peak.mean()),
        "rise_s": float(np.nanmean(rise)),
        "settle_s": float(np.nanmean(settle)),
        "settle_max_s": float(np.nanmax(settle)),
        "sse_mm": float(np.mean(sse)),
        "sse_abs_mm": float(np.mean(np.abs(sse))),
        "sse_max_abs_mm": float(np.abs(sse).max()),
        "jitter_rms_mm": float(np.mean(jitter)),
        "converged": float(np.mean(settle < t[-1] - 1e-9)),
        "n_runs": int(n),
        "by_run": {
            "overshoot_pct": overshoot,
            "overshoot_mm": overshoot_mm,
            "settle_s": settle,
            "sse_mm": sse,
            "jitter_rms_mm": jitter,
            "peak_mm": peak,
        },
    }


# ---------------------------------------------------------------------------
# 研究：参数对比、坡度敏感性、蒙特卡洛
# ---------------------------------------------------------------------------
CONTROLLERS = [
    Gains("P", kp=6.0, ki=0.0, kd=0.0,
          note="纯比例：结构最简单，坡道/阻力留下稳态误差"),
    Gains("PI", kp=6.0, ki=4.0, kd=0.0,
          note="加积分消稳态误差，代价是轻微超调"),
    Gains("PID", kp=6.0, ki=4.0, kd=0.30,
          note="推荐：kd 压超调，稳态误差接近 0"),
    Gains("PI 无抗饱和", kp=6.0, ki=4.0, kd=0.0, windup_guard=False,
          note="反面教材：饱和期积分灌满 → 到点后大幅过冲"),
    Gains("PID@远程200ms", kp=6.0, ki=4.0, kd=0.30, delay_s=0.20,
          note="反例：位置环跑在中枢、经 MQTT 下发 → 超调吃掉精度预算"),
]


def cruise_speed_mm_s(tilt_deg: float, v_max: float = V_MAX,
                      tau_v: float = TAU_V, a_fric: float = A_FRIC,
                      v_eps: float = V_EPS) -> float:
    """给定坡度，电机能维持的最高巡航速度（mm/s）。

    解 (v_max − v)/tau_v + a_dist − a_fric·tanh(v/v_eps) = 0；
    若连最小速度都维持不了就返回 0（爬不动）。
    """
    a_dist = tilt_to_disturbance(tilt_deg)

    def f(v: float) -> float:
        return (v_max - v) / tau_v + a_dist - a_fric * np.tanh(v / v_eps)

    lo, hi = 1e-3, max(v_max, 1e-3)
    if f(lo) <= 0:
        return 0.0
    if f(hi) >= 0:
        return float(v_max)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def study(t_end: float = T_END) -> dict:
    """跑全部参数组的阶跃响应，返回轨迹与指标表。"""
    traces: Dict[str, ControlResult] = {}
    rows: List[dict] = []
    for g in CONTROLLERS:
        res = simulate(g, t_end=t_end, seed=7, delay_s=g.delay_s)
        traces[g.name] = res
        row = {"name": g.name, "kp": g.kp, "ki": g.ki, "kd": g.kd,
               "delay_ms": round(1000 * (DELAY_S if g.delay_s is None else g.delay_s), 1),
               "windup_guard": g.windup_guard, "note": g.note}
        row.update({k: round(float(v), 4) for k, v in res.metrics.items()
                    if k != "by_run"})
        rows.append(row)
    return {
        "target_mm": TARGET_MM,
        "init_err_mm": INIT_ERR_MM,
        "dt_s": DT,
        "t_end_s": float(t_end),
        "params": {
            "mass_kg": 1.6,
            "v_max_mm_s": V_MAX,
            "tau_v_s": TAU_V,
            "a_dist_mm_s2": A_DIST,
            "a_fric_mm_s2": A_FRIC,
            "quant_mm": QUANT_MM,
            "noise_sigma_mm": NOISE_SIGMA_MM,
            "delay_s": DELAY_S,
            "settle_band": SETTLE_BAND,
        },
        "rows": rows,
        "traces": traces,
    }


def tilt_study(tilts_deg=(0.0, 1.0, 2.0, 3.0),
               configs: Optional[List[Gains]] = None,
               t_end: float = 18.0, seed: int = 11) -> dict:
    """稳态误差 vs 杆倾斜角 + 该坡度下的最高巡航速度。

    结论指向：纯 P 在 3° 坡道下稳态误差 3.5 mm，已经吃掉 ±5 mm 预算的 2/3；
    同时 3° 以上巡航速度掉到 33 mm/s 以下（1.1 m 要 33 s），机械上要保证水平。
    """
    cfgs = configs or [CONTROLLERS[0], CONTROLLERS[1], CONTROLLERS[2]]
    rows = []
    for tilt in tilts_deg:
        a_dist = tilt_to_disturbance(tilt)
        v_cruise = cruise_speed_mm_s(tilt)
        row = {"tilt_deg": float(tilt), "a_dist_mm_s2": float(a_dist),
               "cruise_mm_s": float(v_cruise),
               "full_rod_s": float(1100.0 / v_cruise) if v_cruise > 0 else float("inf")}
        for g in cfgs:
            res = simulate(g, a_dist=a_dist, t_end=t_end, seed=seed,
                           delay_s=g.delay_s)
            row[g.name] = {
                "sse_mm": float(res.metrics["sse_mm"]),
                "sse_abs_mm": float(res.metrics["sse_abs_mm"]),
                "settle_s": float(res.metrics["settle_s"]),
            }
        rows.append(row)
    return {
        "tilts_deg": [float(v) for v in tilts_deg],
        "config_names": [g.name for g in cfgs],
        "rows": rows,
        "spec_mm": 5.0,
    }


def monte_carlo(gains: Optional[Gains] = None, n_runs: int = 200,
                seed: int = 20261123) -> dict:
    """蒙特卡洛：编码器噪声、速度环时间常数、速度上限、坡道、初始误差一起抖。"""
    g = gains or CONTROLLERS[2]  # 默认推荐 PID
    rng = np.random.default_rng(seed)
    noise = rng.uniform(0.08, 0.30, n_runs)
    tau = rng.uniform(0.030, 0.050, n_runs)
    vmax = rng.uniform(54.0, 66.0, n_runs)
    adist = rng.uniform(-220.0, -100.0, n_runs)
    x0 = -5.0 + rng.uniform(-0.5, 0.5, n_runs)

    res = simulate(g, n_runs=n_runs, seed=seed, noise_sigma=noise,
                   quant=QUANT_MM, v_max=vmax, tau_v=tau, a_dist=adist, x0=x0)
    br = res.metrics["by_run"]
    ov = br["overshoot_pct"]
    ov_mm = br["overshoot_mm"]
    st = np.nan_to_num(br["settle_s"], nan=float(np.nanmax(br["settle_s"])))
    sse_abs = np.abs(br["sse_mm"])
    jit = br["jitter_rms_mm"]

    def _stat(a: np.ndarray) -> dict:
        return {"mean": float(np.mean(a)), "max": float(np.max(a)),
                "p95": float(np.percentile(a, 95)),
                "std": float(np.std(a))}

    return {
        "gains": g.name,
        "n_runs": int(n_runs),
        "overshoot_pct": _stat(ov),
        "overshoot_mm": _stat(ov_mm),
        "settle_s": _stat(st),
        "sse_abs_mm": _stat(sse_abs),
        "jitter_rms_mm": _stat(jit),
        "by_run": {
            "overshoot_pct": ov,
            "overshoot_mm": ov_mm,
            "settle_s": st,
            "sse_abs_mm": sse_abs,
            "jitter_rms_mm": jit,
        },
        "spread": {
            "noise_sigma_mm": [float(noise.min()), float(noise.max())],
            "tau_v_s": [float(tau.min()), float(tau.max())],
            "v_max_mm_s": [float(vmax.min()), float(vmax.max())],
            "a_dist_mm_s2": [float(adist.min()), float(adist.max())],
            "init_err_mm": [float(x0.min()), float(x0.max())],
        },
    }


__all__ = [
    "Gains",
    "ControlResult",
    "simulate",
    "study",
    "tilt_study",
    "monte_carlo",
    "tilt_to_disturbance",
    "cruise_speed_mm_s",
    "CONTROLLERS",
    "TARGET_MM",
    "INIT_ERR_MM",
    "V_MAX",
    "TAU_V",
    "A_DIST",
    "A_FRIC",
    "QUANT_MM",
    "NOISE_SIGMA_MM",
    "SETTLE_BAND",
    "DELAY_S",
]
