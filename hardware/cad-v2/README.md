# hardware/cad-v2 · 抱箍式伸缩圆柱（锥面收口夹头）

v2 概念：在既有晾衣杆上串 **K+1 个抱箍式伸缩圆柱**，衣架挂在相邻两个端头的 **10 mm 接缝**里。
每个圆柱**两端各有一套锥面收口夹头**（12° 锥面套筒 + 6 段弹性夹头环 + 微动开关）：

- 推套筒 6 mm → 锥面把夹头环径向压紧在杆上（F_hold ≈ 82 N）；拉出即松；
- 锁一端、松另一端 → 只有松的那端伸缩（**单向伸缩**）；
- 两端都锁 → 长度被钉死在杆上（**定点锁定**，断电不掉位）；
- 两端调节器再顶墙 → 整条链预紧（**不用恒力卷簧**）。

## 二、怎么跑

```bash
# 整条链预览（5 个调节器 + 衣架钩环示意）
openscad -D 'PART="assembly"' -o asm.stl hangflow_v2.scad

# 单件
openscad -D 'PART="clamp_half"'   -o clamp.stl   hangflow_v2.scad
openscad -D 'PART="end_head"'     -o head.stl    hangflow_v2.scad
openscad -D 'PART="barrel_half"'  -o barrel.stl  hangflow_v2.scad
openscad -D 'PART="sleeve"'       -o sleeve.stl  hangflow_v2.scad
openscad -D 'PART="cone_sleeve"'  -o cone.stl    hangflow_v2.scad
openscad -D 'PART="collet_ring"'  -o collet.stl  hangflow_v2.scad
openscad -D 'PART="push_knob"'    -o knob.stl    hangflow_v2.scad

# 换杆径（Ø35 现场杆）
openscad -D 'ROD_D=35' -o clamp_35.stl hangflow_v2.scad

# 端部段 E（L 90–110，带顶墙撑脚）
openscad -D 'UNIT="E"' -D 'L_MIN=90' -D 'L_MAX=110' -o e.stl hangflow_v2.scad

# 中距段 M（L 130–190，行程 60）
openscad -D 'UNIT="M"' -D 'L_MIN=130' -D 'L_MAX=190' -o m.stl hangflow_v2.scad

# 一盘打印（一个中间段的全部件）
openscad -D 'PART="print_layout"' -o plate.3mf hangflow_v2.scad
```

OpenSCAD 的 Customizer 里可以直接改 `ROD_D / UNIT / L_MIN / L_MAX / PART`。

## 三、坐标系约定

- 原点 = 杆轴心线与本单元 X 向中点；**X 沿杆**，+X 为右端，Z 向上。
- 接缝在 `X = ±L/2` 之外，两端头 **-Z 方向**挂衣架（U 形托 + Ø5 半销）。
- 两端夹头统一由 **+Z 侧推钮/推杆**驱动，铰链在 -Y 侧，便于单手推拉。

## 四、参数表（改这些）

| 参数 | 默认 | 范围 | 含义 |
|---|---|---|---|
| `ROD_D` | 25 | 20–35 | 目标杆径 |
| `GUIDE_CLEAR` | 0.3 | 0.2–0.8 | 导向单边间隙（松配，不是夹紧量） |
| `SEAM` | 10 | 8–14 | 接缝宽（用户锁定） |
| `PIN_D / PIN_OUT / PIN_GAP` | 5 / 5.0 / 0.5 | — | 半销与防夹手硬限位 |
| `HOOK_DROP` | 21.5 | 19–24 | 销桥低于杆轴的距离（看衣架钩环） |
| `UNIT` | N | N/M/W/E/L | N 窄距 / M 中距 / W 宽距 / **E 端部单元（外端锚定，L 30–120，行程 90）** / **L Lite 被动端件（定长 30/45/60）** |
| `POD_EXTRA` | 30 | 30 | 锚定挂包比行程多出的轴向（螺母12+轴承8+余量10） |
| `POD_CLEAR` | 20 | 20 | 挂包前端到墙/障碍的余量；安装要求锚定点离墙 ≥ POD_LEN+20 = 140 |
| `CONE_ANGLE` | 12 | 10–15 | 锥半角；放大比 = cot(θ+φ) |
| `SLEEVE_STROKE` | 6.0 | 5–8 | 套筒轴向行程；径向收口 = 行程×tanθ |
| `COLLET_SLOTS` | 6 | 6 | 5 半槽 + 1 全开缝（能掰开扣杆） |
| `PUSH_F` | 40 | 30–50 | 轴向推力设计值；N_r = PUSH_F×cot(θ+φ) ≈ 117 N |
| `L_MIN / L_MAX` | 100 / 130 | 25–240 | 长度范围；`STROKE = L_MAX-L_MIN`（E 段默认 30 / 120） |
| `C_L` | 70 | 70 | 中间段除行程外固定长度 = 2×夹头16 + 螺母12 + 轴承8 + 电机轴向14 + 余量4 |
| `C_POD` | 30 | 30 | 端部单元净距里的固定部分（内端头6 + 最小重叠24）；挂包长 = STROKE+30 |

派生量自动算：`BARREL_OD = ROD_D + 2*(GUIDE_CLEAR+WALL_S+NUT_SLOT+2*NUT_HALF+WALL)`。
Ø25 杆 → 外径 **Ø65.8**（取 Ø66）。

## 五、防呆（assert 都写了什么）

1. 杆径必须在 20–35；
2. 导向间隙 0.2–0.8（小于 0.2 是夹死、大于 0.8 会晃）；
3. `L_MAX > L_MIN` 且在 45–230；
4. **`STROKE <= L_MIN - C_L`（中间段，C_L=70）** 或 **`STROKE <= POD_LEN - 30`（E 端部单元）**——行程装不下就报错（中间段想要 50 mm 行程，L_MIN 至少要 120；E 端部 90 mm 行程由 120 mm 挂包承担）；
5. 端部单元：`L_MIN ≥ 30`、`STROKE ≤ 90`；Lite：`L_MAX == L_MIN`（必须是定长）；
5. 接缝 8–14 mm；
6. **`PIN_GAP >= 0.3`**——防夹手硬限位不许归零；
7. 外径 ≤85（过肥说明螺母/壁厚选错）；
8. 丝杆偏心必须让开内管；
9. `PART` 取值无效直接断言失败，并列出合法值。

## 六、和文档的对应

| CAD 模块 | 文档章节 | 说明 |
|---|---|---|
| `clamp_half / clamp_ring` | §2、§6.1 | 两半端头、铰链、卡扣、夹头座腔、微动开关槽、止退缺口 |
| `cone_sleeve` | §2.2 | 12° 内锥套筒，行程 6 mm，Ø68（管 Ø66 +2） |
| `collet_ring` | §2.2、§2.4 | 6 段 TPU 夹头环（5 半槽 + 1 全开缝），可掰开扣杆 |
| `push_knob` | §2.2 | 3:1 手动推钮；P1 换电磁推杆（同接口） |
| `end_head` | §5 | U 形托 + 半销 + 缓冲垫槽 + 编码牌 |
| `barrel_half / sleeve` | §3、§4 | 外管、内管骨架、螺母座、丝杆偏心通道 |
| `wall_foot` | §2.1 W 态 | 顶墙撑脚，行程 25 mm |
| `anchor_pod / lite_end` | §3.2、§4.6 | 端部锚定挂包（朝墙，藏 90 mm 行程）/ Lite 定长端件 |
| `chain_preview` | §1.1 | 墙—调节器—衣—…—墙，K+1 个（要看端部单元就把 `UNIT="E"`） |

## 七、还没做的

- 齿条/同步带（横置电机 → 丝杆的转向件）只在参数里留了空间，没建实体；
- 微动开关只开了槽，没建模型；
- 打印件的收缩补偿（PETG 约 0.4%）未加到孔位，打样第一版按名义尺寸，量了再改。
