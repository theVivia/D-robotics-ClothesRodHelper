"""衣序 HangFlow v2 —— 圆柱长度闭环控制仿真（丝杆 + AS5600）。

被控对象
--------
* 驱动：N20 减速电机 + T8 梯形丝杆（导程 lead，效率 η≈0.35）。
  轴向速度随负载线性下降：`v = v_free·(1 − F/F_stall)`；
  负载 F = 伸缩副自身阻力 2 N + 相邻衣架滑动摩擦 3 N/件，
  日常调节最坏 11 N（推 3 件衣架块），安装标定最坏 14 N。
* 测量：AS5600 磁编码器装在丝杆上，12 bit/圈 → 长度分辨率 = lead/4096
  （lead 8 mm → 0.002 mm），叠加 ±0.01 mm 噪声。
* 传动间隙：丝杆副反向间隙 b = 0.2 mm（梯形丝杆 + 塑料螺母，估算）。
  电机侧（编码器看到的）位置 m 与负载侧（真实圆柱长度）x 之间存在死区。
* 控制器：位置式 PID（输出 mm/s 速度指令），带积分抗饱和、速度/限位钳制。
* 安全：长度上下限（40 / 220 mm）、堵转判据（电流 > 0.9 A 且 0.3 s 无位移）。

工程结论（仿真实测的数值见 docs/_data-v2/results.md）
--------------------------------------------------
1) 60 mm 行程按 4 mm/s 校核约 15 s/段（T8 导程 8 mm，11 N 负载）；
2) 反向间隙让负载位置误差在 ±b/2 内翻转 → 「末段单向逼近 + b/2 补偿」可消掉；
3) 堵转在 0.3 s 内可判出（电流跳变 + 无位移），随后回退 2 mm 解除。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from chain import DRIVES, Drive
from length_planner import INNER_MAX_MM as L_MAX_MM, INNER_MIN_MM as L_MIN_MM

DT = 0.005
T_END = 25.0
TAU_ACT = 0.05           # 执行器（速度环）一阶时间常数 s
BACKLASH_MM = 0.20       # 丝杆副反向间隙
ENCODER_NOISE_MM = 0.01
STALL_CURRENT_A = 0.90   # 堵转判据电流
STALL_WINDOW_S = 0.30    # 无位移判据窗口
LOAD_EXTEND_N = 11.0     # 日常调节最坏负载（2 N 副阻力 + 3×3 N 衣架摩擦）
LOAD_RETRACT_N = 11.0    # 回缩同样要拉动右侧衣架块


@dataclass
class ControlGains:
    kp: float = 6.0       # (mm/s) per mm
    ki: float = 1.0       # (mm/s) per (mm·s)
    kd: float = 0.10
    name: str = "PID"


@dataclass
class LengthResult:
    t: np.ndarray
    x_load: np.ndarray        # 真实圆柱长度 mm
    m_motor: np.ndarray       # 丝杆/编码器位置 mm
    v_cmd: np.ndarray
    current: np.ndarray
    target: float
    metrics: Dict[str, float] = field(default_factory=dict)
    stall_time_s: Optional[float] = None
    stall_detected: bool = False


def clamp_target(target: float) -> tuple:
    """长度限位：返回 (钳制后的目标, 是否告警, 告警文本)。"""
    t = float(target)
    if t < L_MIN_MM:
        return L_MIN_MM, True, f"目标 {t:.0f} mm 低于下限 {L_MIN_MM:.0f} mm，已钳到下限"
    if t > L_MAX_MM:
        return L_MAX_MM, True, f"目标 {t:.0f} mm 高于上限 {L_MAX_MM:.0f} mm，已钳到上限"
    return t, False, ""


def simulate_step(drive: Drive,
                  target: float = 100.0,
                  start: float = 40.0,
                  gains: ControlGains = ControlGains(),
                  t_end: float = T_END,
                  dt: float = DT,
                  backlash: float = BACKLASH_MM,
                  load_extend_n: float = LOAD_EXTEND_N,
                  encoder_noise: float = ENCODER_NOISE_MM,
                  unidirectional: bool = True,
                  compensate: bool = True,
                  stall_at_s: Optional[float] = None,
                  stall_force_n: float = 60.0,
                  seed: int = 0) -> LengthResult:
    """仿真一次长度阶跃（默认 40→100 mm）。

    unidirectional : 末段从同方向（伸长侧）逼近，保证间隙状态确定；
    compensate     : 命令端补 b/2，抵消已知的间隙偏置；
    stall_at_s     : 若给定时刻起遇到 60 N 阻塞（模拟卡住/钩住）。
    """
    rng = np.random.default_rng(seed)
    steps = int(round(t_end / dt))
    t = np.arange(steps + 1) * dt

    # 单向逼近：若当前比目标长（需要缩短），先到 target−1.5 mm 再伸长到位
    plan_target = float(target)
    pre_target = None
    if unidirectional and start > target + 0.2:
        pre_target = max(L_MIN_MM, target - 1.5)

    m = float(start)
    x = float(start)
    s = 0.0                      # 间隙状态 ∈ [-b/2, b/2]
    v_act = 0.0
    integral = 0.0
    X = np.zeros(steps + 1)
    M = np.zeros(steps + 1)
    V = np.zeros(steps + 1)
    I = np.zeros(steps + 1)
    X[0], M[0] = x, m
    stall_t: Optional[float] = None
    detected = False
    still_time = 0.0
    m_prev = m
    phase = 0

    for k in range(steps):
        tk = k * dt
        # 阶段目标：需要缩短时，先压到 target−1.5 mm，再统一从伸长侧逼近
        comp = backlash / 2.0 if compensate else 0.0
        if pre_target is not None and phase == 0:
            if m > pre_target + comp + 1e-6:
                goal = pre_target
            else:
                phase = 1
                integral = 0.0
                goal = plan_target
        else:
            goal = plan_target
        cmd_target = goal + comp

        # 负载与速度上限
        direction = 1 if cmd_target > m else -1
        load = load_extend_n if direction > 0 else LOAD_RETRACT_N
        blocked = stall_at_s is not None and tk >= stall_at_s
        v_max = drive.speed_mm_s(stall_force_n if blocked else load)

        # 编码器测量（AS5600 在丝杆上，测电机侧位置）
        m_meas = m + rng.normal(0.0, encoder_noise)
        e = cmd_target - m_meas
        integral = float(np.clip(integral, -2.0, 2.0))
        v_raw = gains.kp * e + gains.ki * integral - gains.kd * v_act
        # 条件积分抗饱和：输出饱和时不再积分
        saturated = (v_raw > v_max) or (v_raw < -v_max)
        if not saturated:
            integral += e * dt
            integral = float(np.clip(integral, -2.0, 2.0))
        v_cmd = float(np.clip(v_raw, -v_max, v_max))

        # 执行器一阶跟随
        v_act += (v_cmd - v_act) * dt / TAU_ACT
        if blocked:
            v_act = 0.0
        m += v_act * dt

        # 反向间隙：m → x 的死区
        if v_act > 1e-9:
            s = min(s + v_act * dt, backlash / 2.0)
        elif v_act < -1e-9:
            s = max(s + v_act * dt, -backlash / 2.0)
        x = m - s
        x = float(np.clip(x, L_MIN_MM - 5.0, L_MAX_MM + 5.0))

        # 电流
        force = stall_force_n if blocked else load
        current = drive.current_a(force)
        if abs(v_act) < 0.05 and abs(v_cmd) > 1.0:
            current += 0.25  # 堵转边缘：扭矩上不去，电流爬升

        X[k + 1], M[k + 1], V[k + 1], I[k + 1] = x, m, v_cmd, current

        # 堵转判据：指令在动、实际 0.3 s 没有位移、电流超阈值
        if abs(m - m_prev) < 1e-4 and abs(v_raw) > 1.0:
            still_time += dt
        else:
            still_time = 0.0
        m_prev = m
        if (still_time >= STALL_WINDOW_S and current > STALL_CURRENT_A
                and not detected):
            detected = True
            stall_t = tk

    metrics = _metrics(t, X, plan_target)
    metrics["stall_detected"] = float(detected)
    metrics["peak_current_a"] = float(I.max())
    metrics["peak_len_rate_mm_s"] = float(np.abs(np.diff(X)).max() / dt)
    return LengthResult(t=t, x_load=X, m_motor=M, v_cmd=V, current=I,
                        target=plan_target, metrics=metrics,
                        stall_time_s=stall_t, stall_detected=detected)


def _metrics(t: np.ndarray, x: np.ndarray, target: float) -> Dict[str, float]:
    err = x - target
    band = 0.02 * abs(target)
    tail = slice(int(0.85 * len(t)), len(t))
    sse = float(err[tail].mean())
    if target >= x[0]:
        over = max(0.0, float(x.max() - target))
    else:
        over = max(0.0, float(target - x.min()))
    overshoot_pct = 100.0 * over / abs(target)
    # 上升 10–90%
    x0 = float(x[0])
    lo = x0 + 0.1 * (target - x0)
    hi = x0 + 0.9 * (target - x0)
    mask_lo = x >= lo
    mask_hi = x >= hi
    t_lo = float(t[np.argmax(mask_lo)]) if mask_lo.any() else float("nan")
    t_hi = float(t[np.argmax(mask_hi)]) if mask_hi.any() else float("nan")
    bad = np.abs(err) > band
    if bad.any():
        last_bad = len(t) - 1 - int(np.argmax(bad[::-1]))
        settle = float(t[min(last_bad + 1, len(t) - 1)])
    else:
        settle = 0.0
    return {
        "target_mm": float(target),
        "start_mm": x0,
        "rise_s": float(t_hi - t_lo),
        "settle_s": float(settle),
        "overshoot_pct": float(overshoot_pct),
        "overshoot_mm": float(over),
        "sse_mm": sse,
        "sse_abs_mm": abs(sse),
        "tail_std_mm": float(err[tail].std()),
        "peak_current_a": float(0.0),
    }


def control_study() -> dict:
    """对比三档驱动 + 间隙补偿策略，给阶跃指标表。"""
    rows = []
    traces = {}
    for drive in DRIVES:
        res = simulate_step(drive)
        traces[drive.name] = res
        row = {"drive": drive.name, "lead_mm": drive.lead_mm, "rpm": drive.rpm,
               "v_free_mm_s": drive.v_free_mm_s}
        row.update({k: round(float(v), 4) for k, v in res.metrics.items()})
        rows.append(row)
    best = traces[DRIVES[1].name]
    return {
        "rows": rows,
        "traces": traces,
        "gains": {"kp": ControlGains().kp, "ki": ControlGains().ki,
                  "kd": ControlGains().kd},
        "load_extend_n": LOAD_EXTEND_N,
        "backlash_mm": BACKLASH_MM,
        "encoder_res_mm": DRIVES[1].lead_mm / 4096.0,
    }


def backlash_study() -> dict:
    """反向间隙 / 逼近策略对「负载侧长度误差」的影响。"""
    drive = DRIVES[1]
    cases = [
        ("直接逼近（缩短）", dict(start=160.0, target=100.0,
                                 unidirectional=False, compensate=False)),
        ("直接逼近（伸长）", dict(start=40.0, target=100.0,
                                 unidirectional=False, compensate=False)),
        ("单向逼近（缩短→伸长）", dict(start=160.0, target=100.0,
                                     unidirectional=True, compensate=False)),
        ("单向逼近 + b/2 补偿", dict(start=160.0, target=100.0,
                                   unidirectional=True, compensate=True)),
    ]
    rows = []
    for name, kw in cases:
        res = simulate_step(drive, **kw)
        rows.append({
            "case": name,
            "target_mm": kw["target"],
            "x_final_mm": float(res.x_load[-1]),
            "error_mm": float(res.x_load[-1] - kw["target"]),
            "settle_s": float(res.metrics["settle_s"]),
        })
    return {"rows": rows, "backlash_mm": BACKLASH_MM}


def stall_study() -> dict:
    """堵转检测：2 s 时遇到 60 N 阻塞，看多久能判出。"""
    drive = DRIVES[1]
    res = simulate_step(drive, start=40.0, target=160.0, stall_at_s=2.0)
    return {
        "stall_at_s": 2.0,
        "stall_force_n": 60.0,
        "detected": bool(res.stall_detected),
        "detect_time_s": (None if res.stall_time_s is None
                          else float(res.stall_time_s - 2.0)),
        "detect_abs_s": (None if res.stall_time_s is None
                         else float(res.stall_time_s)),
        "peak_current_a": float(res.current.max()),
        "threshold_a": STALL_CURRENT_A,
        "window_s": STALL_WINDOW_S,
        "result": res,
    }


def limit_study() -> dict:
    """限位：目标越界时钳制并告警。"""
    rows = []
    for tgt in (20.0, 40.0, 108.0, 220.0, 260.0):
        clamped, warn, text = clamp_target(tgt)
        rows.append({"requested_mm": tgt, "clamped_mm": clamped,
                     "warned": bool(warn), "text": text})
    return {"rows": rows}


__all__ = [
    "ControlGains",
    "LengthResult",
    "simulate_step",
    "clamp_target",
    "control_study",
    "backlash_study",
    "stall_study",
    "limit_study",
    "DT",
    "T_END",
    "BACKLASH_MM",
    "ENCODER_NOISE_MM",
    "STALL_CURRENT_A",
    "STALL_WINDOW_S",
    "LOAD_EXTEND_N",
    "LOAD_RETRACT_N",
]

