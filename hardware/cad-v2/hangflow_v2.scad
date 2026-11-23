// =============================================================================
//  衣序 HangFlow v2 · 抱箍式伸缩圆柱（双端夹持）—— 参数化主件（OpenSCAD）
// =============================================================================
//  这份文件干什么：把"调节器"的全部机械件用参数算出来。改 ROD_D / L_MIN / L_MAX
//  就能重生成 N/M/W/E/S 五档规格，以及装配预览和打印排版。
//
//  结构（从杆轴心向外）：杆 → 0.3 单边导向间隙 + PTFE 片 → 内管骨架 → 螺母座
//  → T8×8 丝杆（偏心 e）→ 外管 → 端头两半（铰链 + 卡扣 + 锥面收口夹头）。
//
//  坐标系：原点 = 杆轴心线与本单元 X 向中点；X 沿杆；Z 向上；Y 垂直于杆。
//    - +X 是"右端"，-X 是"左端"；两端各一套锥面收口夹头（推钮在 +Z 侧）
//    - 接缝在 X = ±L/2 之外；端头在 -Z 方向挂衣架（U 形托 + Ø5 半销）
//    - 电机横置在外管前上方（+Z 偏置），锥齿轮转向丝杆（见 docs/v2/01 §3.2）
//
//  用法（没装 OpenSCAD 也能读）：
//    openscad -D 'PART="assembly"'      -o asm.stl      hangflow_v2.scad
//    openscad -D 'PART="clamp_half"'    -o clamp.stl    hangflow_v2.scad
//    openscad -D 'PART="print_layout"'  -o plate.3mf   hangflow_v2.scad
//    openscad -D 'ROD_D=32' -D 'UNIT="M"' -D 'L_MIN=130' -D 'L_MAX=190' -o m_32.stl hangflow_v2.scad
//    Customizer 里直接改参数即可，PART 下拉切换零件。
//
//  ★ 打印预算（0.4 喷嘴 / 0.2 层 / 3 壁 / 25% 填充，PETG）：
//      夹持端环两半 26 g / 1.3 h  ×2 ；外管两半 30 g / 1.6 h ；内管骨架 14 g / 0.8 h
//      端头 12 g / 0.7 h ；锥面套筒 12 g / 0.6 h ；夹头环 8 g / 0.5 h ；顶墙撑脚 8 g / 0.5 h（仅端部段）
//    ★ 单中间段 ≈ 95 g / 4.2 h，全部悬垂 ≤45°，孔为通孔，不需要支撑。
//  ★ 关键配合：铰链销孔 Ø2.1；锥面 12°（Ra1.6）；套筒行程 6.0；微动开关槽 3.2×2.0；
//      半销孔 Ø5.2；TPU 摩擦块槽 60×8×3.2；轴承位 Ø8（压入）。
// =============================================================================

/* [杆与夹持 —— 改这一组就能换杆径] */
ROD_D        = 25;      // [20:0.5:35] 目标杆径 (mm)，现场按实际杆量一次；演示 Ø25
GUIDE_CLEAR  = 0.3;     // 导向间隙单边 (mm)：松配导向，松开夹持才能滑
WALL         = 2.5;     // 外管壁厚 (mm)
WALL_S       = 2.0;     // 内管骨架壁厚 (mm)
NUT_SLOT     = 0.6;     // 螺母座与内管外圆的间隙 (mm)
NUT_HALF     = 7.5;     // T8 螺母座半宽 (mm)：AF15 的一半
SEAM         = 10;      // 接缝宽度 (mm) —— 用户锁定值，衣架钩占满
PIN_D        = 5;       // 半销直径 (mm)
PIN_OUT      = 5.0;     // 半销伸出端面长度 (mm)
PIN_GAP      = 0.5;     // 两半销端面机械间隙 (mm) —— 防夹手硬限位，不许改 0
HOOK_DROP    = 21.5;    // 销桥中心低于杆轴 (mm)：衣架钩环内 R18–22 的最佳位置

/* [长度规格 —— N 窄距 / M 中距 / W 宽距 / E 端部段 / S 被动短套] */
UNIT         = "N";     // [N, M, W, E, S]  N 窄距 / M 中距 / W 宽距 / E 端部段 / S 被动短套
L_MIN        = 100;     // [45:5:230] 最短长度 (mm)；N 默认 100，M 130，W 190，E 90
L_MAX        = 130;     // [55:5:240] 最长长度 (mm)；N 默认 130，M 190，W 220，E 110
STROKE       = L_MAX - L_MIN;
C_L          = 70;      // 除行程外的固定长度 = 2×夹持环16 + 螺母12 + 轴承8 + 电机轴向14 + 余量4
CLAMP_W      = 16;      // 夹持端头轴向宽 (mm)：套筒行程 6 + 铰链 + 卡扣塞得下的下限

/* [锥面收口夹头（Collet）] */
CONE_ANGLE   = 12;      // [10:1:15] 锥半角 (deg)：越小放大越大，但太易自锁/卡死
CONE_MU      = 0.12;    // 锥面摩擦系数：放大比 = cot(θ+φ)
SLEEVE_STROKE= 6.0;     // [5:0.5:8] 套筒轴向行程 (mm)；径向收口 = 行程×tanθ
COLLET_SLOTS = 6;       // 夹头段数：5 条半槽 + 1 条全开缝（能掰开扣杆）
COLLET_WALL  = 3.5;     // 夹头环壁厚 (mm)
COLLET_LEN   = 20;      // 夹头环轴向长 (mm)
COLLET_BORE  = 0.9;     // 松态内孔比杆大的量 (mm)：0.9 才掰得进去
PUSH_F       = 40;      // 轴向推力设计值 (N)（30–50）：N_r = PUSH_F×cot(θ+φ)
DETENT_DROP  = 0.8;     // 止退缺口深度 (mm)：吃住夹头回弹

/* [端部] */
WALL_FOOT    = true;    // 端部段是否画顶墙撑脚
FOOT_TRAVEL  = 25;      // 撑脚行程 (mm)
FOOT_D       = 28;      // 撑脚垫直径 (mm)

/* [零件选择] */
PART         = "assembly";  // [assembly, clamp_half, clamp_ring, cone_sleeve, collet_ring, push_knob, end_head, barrel_half, sleeve, wall_foot, print_layout, dimensions]
$fn          = 64;

// ---------------------------------------------------------------------------
// 派生尺寸（统一从这里取，别在模块里硬编码）
// ---------------------------------------------------------------------------
R_ROD     = ROD_D / 2;
R_BORE    = R_ROD + GUIDE_CLEAR;
R_SLEEVE  = R_BORE + WALL_S;
SCREW_OFF = R_SLEEVE + NUT_SLOT + NUT_HALF;          // 丝杆偏心 e
R_OUT     = SCREW_OFF + NUT_HALF + WALL;             // 外管外半径
BARREL_OD = 2 * R_OUT;
SEAM_HALF = SEAM / 2;
L_HALF    = L_MIN / 2;                               // 装配预览画最短态（最挤的工况）

// 防呆：参数不对就在生成前报错，别打出一个装不上杆的件
assert(ROD_D >= 20 && ROD_D <= 35,
       str("ROD_D 必须落在 20–35 mm，当前 ", ROD_D));
assert(GUIDE_CLEAR >= 0.2 && GUIDE_CLEAR <= 0.8,
       "GUIDE_CLEAR 必须 0.2–0.8 mm：小于 0.2 是夹死，大于 0.8 会晃");
assert(L_MIN >= 45 && L_MAX <= 230 && L_MAX > L_MIN,
       str("L 超出 45–230 或 L_MAX<=L_MIN：L_MIN=", L_MIN, " L_MAX=", L_MAX));
assert(STROKE <= L_MIN - C_L,
       str("行程超结构下限：STROKE=", STROKE, " 必须 <= L_MIN-C_L=", L_MIN - C_L,
           "（L_MIN = STROKE + 70）。改小行程或加长 L_MIN，否则丝杆/螺母/电机装不进外管"));
assert(SEAM >= 8 && SEAM <= 14,
       str("SEAM 必须 8–14 mm（衣架厚 10 + 公差），当前 ", SEAM));
assert(PIN_GAP >= 0.3,
       "PIN_GAP 不许小于 0.3 mm：那是防夹手机械硬限位");
assert(BARREL_OD <= 85,
       str("外径 ", BARREL_OD, " 过肥（>85），检查 NUT_HALF/WALL 或换小丝杆"));
assert(SCREW_OFF > R_SLEEVE + PIN_D,
       "丝杆偏心必须让开内管，否则螺母撞管");
// 锥面收口夹头的三条硬约束
assert(CONE_ANGLE >= 10 && CONE_ANGLE <= 15,
       str("锥半角必须 10–15°（太小自锁/卡死，太大夹不紧），当前 ", CONE_ANGLE));
assert(SLEEVE_STROKE >= 5 && SLEEVE_STROKE <= 8,
       str("套筒行程必须 5–8 mm，当前 ", SLEEVE_STROKE));
assert(COLLET_SLOTS == 6,
       "夹头必须 6 段（5 条半槽 + 1 条全开缝）：少一条就掰不开、扣不上杆");
echo(str("BARREL_OD=", BARREL_OD, "  SCREW_OFF=", SCREW_OFF,
         "  STROKE=", STROKE, "  L=", L_MIN, "..", L_MAX));
echo(str("锥面放大比 cot(θ+φ)=", 1 / tan(CONE_ANGLE + atan(CONE_MU)),
         "  径向夹紧 N_r=", PUSH_F / tan(CONE_ANGLE + atan(CONE_MU)),
         " N  径向收口=", SLEEVE_STROKE * tan(CONE_ANGLE), " mm"));

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------
module ring(r_out, r_in, h, c = true) {
    difference() {
        cylinder(r = r_out, h = h, center = c);
        cylinder(r = r_in,  h = h + 0.2, center = c);
    }
}

// 绕 X 轴放置的圆柱（沿杆方向的轴都这么画）
module cyl_x(r, l, x = 0, y = 0, z = 0) {
    translate([x, y, z]) rotate([0, 90, 0]) cylinder(r = r, h = l, center = true);
}

// ---------------------------------------------------------------------------
// A. 端头/夹持座两半（打开状态；两半结构相同，靠铰链/卡扣合拢）
//    - 内弧贴 PTFE 片（槽 0.6 深），侧向两道 TPU 防摆筋
//    - 内腔装弹性夹头环；-X 侧留锥面套筒的导向轨道
//    - -Y 侧铰链耳；+Y 侧卡扣；+Z 侧微动开关槽与止退缺口
// ---------------------------------------------------------------------------
module clamp_half() {
    difference() {
        union() {
            // 半环本体（只保留 +Y 半，其余切片全尺寸，避免切掉象限）
            intersection() {
                ring(R_OUT + 4, R_BORE, CLAMP_W);
                translate([0, (R_OUT + 10) / 2, 0])
                    cube([2 * R_OUT + 20, R_OUT + 10, CLAMP_W + 2], center = true);
            }
            // 套筒导向轨道（两条，-X 端，套筒沿它滑 6 mm）
            for (sy = [-1, 1])
                translate([-CLAMP_W / 2 - 3, sy * (R_OUT - 2), 0])
                    cube([10, 6, 8], center = true);
            // 铰链耳（-Y）：三耳，中间留销孔
            for (sx = [-1, 0, 1]) {
                translate([sx * 9, -(R_OUT + 5), 0])
                    difference() {
                        cube([8, 12, 10], center = true);
                        translate([0, 1, 0]) rotate([0, 90, 0])
                            cylinder(r = 1.05, h = 12, center = true);  // Ø2.1 销孔
                    }
            }
            // 卡扣（+Y 侧上方）：悬臂钩
            translate([0, R_OUT + 4, R_BORE + 2]) cube([8, 26, 3], center = true);
        }
        // PTFE 片槽（内弧，靠下侧承力）
        ring(R_BORE + 0.62, R_BORE - 0.01, CLAMP_W - 4);
        // 夹头环座腔（Ø = 杆 + 2×夹头壁 + 0.4）
        translate([0, 0, 0])
            cylinder(r = R_ROD + COLLET_BORE + COLLET_WALL + 0.4, h = COLLET_LEN, center = true);
        // 窗口减重
        for (sx = [-1, 1]) for (ay = [30, 75]) {
            translate([sx * 6, 0, 0])
                rotate([0, 0, -ay]) translate([0, R_OUT + 1, 0])
                    cylinder(r = 5, h = CLAMP_W + 2, center = true, $fn = 24);
        }
        // 微动开关槽 + 止退缺口（套筒推到 4.5–6 mm 时弹片落入）
        translate([0, R_OUT + 3, 10]) cube([10, 6, 4], center = true);
        translate([CLAMP_W / 2 - 1.5, 0, R_OUT - 3]) cube([3, 10, DETENT_DROP], center = true);
    }
}

module clamp_ring() {
    // 合拢状态（仅预览用）
    clamp_half();
    rotate([0, 0, 180]) clamp_half();
}

// ---------------------------------------------------------------------------
// B. 锥面收口套筒（两半）：内锥 12°，轴向内滑 6 mm 把夹头径向压紧
//    外径只比管体大 2 mm（Ø68 vs Ø66）——无外露爪子
// ---------------------------------------------------------------------------
module cone_sleeve() {
    r_cone_big   = R_ROD + COLLET_BORE + COLLET_WALL + 3.2;   // 锥面大端半径
    r_cone_small = R_ROD + COLLET_BORE + COLLET_WALL + 0.2;   // 小端 = 压紧态
    r_sleeve_out = R_OUT + 2;                                  // Ø68 @ ROD25
    difference() {
        union() {
            // 外套筒体（整圈，不做象限裁剪）
            ring(r_sleeve_out, r_cone_small, 12);
            // 推钮（+Z，3:1 拨钮的着力点）
            translate([0, 0, r_sleeve_out]) cube([10, 14, 6], center = true);
        }
        // 12° 内锥（只削内孔的上半，示意锥面）
        translate([0, 0, 4]) cylinder(r1 = r_cone_small, r2 = r_cone_big,
                                     h = SLEEVE_STROKE + 4, center = false, $fn = 64);
        // 导向销槽
        for (sy = [-1, 1])
            translate([0, sy * r_sleeve_out, 0]) cylinder(r = 1.2, h = 20, center = true, $fn = 24);
    }
}

// ---------------------------------------------------------------------------
// C. 弹性夹头环：6 段（5 条半槽 + 1 条全开缝），掰开能扣上杆
// ---------------------------------------------------------------------------
module collet_ring() {
    r_in  = R_ROD + COLLET_BORE;             // 松态内孔 = 杆 + 0.9
    r_out = r_in + COLLET_WALL;
    difference() {
        cylinder(r = r_out, h = COLLET_LEN, center = true, $fn = 72);
        // 内孔
        cylinder(r = r_in, h = COLLET_LEN + 2, center = true, $fn = 72);
        // 轴向半槽：5 条（留 1 段当"全开缝"）
        for (i = [0 : COLLET_SLOTS - 2]) {
            a = i * 360 / COLLET_SLOTS;
            rotate([0, 0, a])
                translate([0, r_out / 2 + 1.2, 0])
                    cube([COLLET_WALL + 2.4, 1.6, COLLET_LEN + 2], center = true);
        }
        // 全开缝（最后一条切到底，两半可掰开）
        rotate([0, 0, (COLLET_SLOTS - 1) * 360 / COLLET_SLOTS])
            translate([0, r_out / 2 + 0.6, 0])
                cube([COLLET_WALL + 3, 2.2, COLLET_LEN + 2], center = true);
        // 抱紧面 6 片（TPU 打印时自带，这里示意 6 个凹槽）
        for (i = [0 : COLLET_SLOTS - 1])
            rotate([0, 0, i * 360 / COLLET_SLOTS + 30])
                translate([0, r_in - 0.4, 0])
                    cube([6, 1.0, 14], center = true);
    }
}

// ---------------------------------------------------------------------------
// D. 手动推钮（3:1 拨杆，手力 15 N → 套筒 45 N）
// ---------------------------------------------------------------------------
module push_knob() {
    hull() {
        translate([0, 0, 0]) cylinder(r = 4.0, h = 6, center = true, $fn = 32);
        translate([26, 0, 0]) rotate([0, 90, 0]) cylinder(r = 3.2, h = 6, center = true, $fn = 32);
    }
    translate([-3, 0, 0]) cylinder(r = 2.2, h = 8, center = true, $fn = 24);  // 与套筒的铰接孔
}

// ---------------------------------------------------------------------------
// C. 端头：Ø66 端盘 + 下方 U 形托 + Ø5 半销 + 顶部夹持对接面
// ---------------------------------------------------------------------------
module end_head(hand = "L") {
    sx = (hand == "R") ? 1 : -1;
    difference() {
        union() {
            // 端盘（带半销座凸台）
            ring(R_OUT, R_BORE, 13);
            // 下方 U 形托：两侧壁 + 底座，托住半销
            translate([0, 0, -HOOK_DROP]) {
                // 底座
                translate([0, 0, -7]) cube([13, 26, 6], center = true);
                // 两侧壁（挡衣架钩环横向窜动）
                for (sy = [-1, 1])
                    translate([0, sy * 11, 0]) cube([13, 4, 8], center = true);
                // U 槽底弧（半销落座 R2.6）
                translate([0, 0, 2.2]) rotate([0, 90, 0])
                    cylinder(r = 2.6, h = 14, center = true);
            }
            // 半销座凸台（伸出端面 PIN_OUT）
            translate([sx * (6.5 + PIN_OUT / 2), 0, -HOOK_DROP])
                rotate([0, 90, 0]) cylinder(r = 4.2, h = PIN_OUT + 1, center = true);
            // 端面缓冲垫槽（3 mm TPU）—— 防夹手第二道
            translate([sx * 7.5, 0, 0]) ring(R_OUT - 4, R_BORE + 2, 2);
        }
        // 半销孔（Ø5.2）+ 收口
        translate([sx * (6.5 + PIN_OUT / 2), 0, -HOOK_DROP])
            rotate([0, 90, 0]) cylinder(r = PIN_D / 2 + 0.1, h = 30, center = true);
        // 编码牌凹槽
        translate([0, 0, R_OUT - 1.6]) rotate([90, 0, 0])
            linear_extrude(height = 0.8, center = true) square([18, 12], center = true);
    }
    // 半销本体（金属件，预览时画出来）
    translate([sx * (6.5 + PIN_OUT / 2), 0, -HOOK_DROP])
        rotate([0, 90, 0]) cylinder(r = PIN_D / 2, h = 12, center = true, $fn = 32);
}

// ---------------------------------------------------------------------------
// D. 外管两半 / 内管骨架
// ---------------------------------------------------------------------------
module barrel_half(len = 80) {
    difference() {
        intersection() {
            ring(R_OUT, R_SLEEVE + 0.25, len);
            translate([0, 0, -1]) cube([2 * R_OUT + 20, 2 * R_OUT + 20, len + 2]);
        }
        // 电机仓（横置于 +Z，径向）
        translate([0, 0, R_SLEEVE + 9]) rotate([90, 0, 0])
            cylinder(r = 7, h = 34, center = true);
        // 丝杆通道（偏心 SCREW_OFF）
        hull() for (sx = [-1, 1])
            translate([sx * (len / 2 - 12), 0, -SCREW_OFF])
                rotate([0, 90, 0]) cylinder(r = 5.2, h = 0.2, center = true);
        // 合模螺钉沉孔
        for (sx = [-1, 1]) for (sy = [-1, 1])
            translate([sx * (len / 2 - 8), sy * (R_OUT - 4), 0])
                rotate([90, 0, 0]) cylinder(r = 1.6, h = 20, center = true);
    }
}

module sleeve(len = 60) {
    // 三筋骨架：省料、抗弯
    difference() {
        union() {
            for (a = [0, 120, 240])
                rotate([0, 0, a]) translate([0, (R_SLEEVE + R_BORE) / 2, 0])
                    cube([WALL_S * 2, R_SLEEVE - R_BORE, len], center = true);
            // 螺母座
            translate([0, 0, -SCREW_OFF]) difference() {
                cube([22, 18, 16], center = true);
                rotate([0, 90, 0]) cylinder(r = 4.3, h = 24, center = true);
            }
        }
        // 导向衬套槽
        ring(R_BORE + 0.62, R_BORE - 0.01, len - 6);
    }
}

// ---------------------------------------------------------------------------
// E. 顶墙撑脚（仅端部段）
// ---------------------------------------------------------------------------
module wall_foot() {
    difference() {
        union() {
            hull() for (sx = [-1, 1])
                translate([sx * 20, 0, -R_OUT + 4]) rotate([0, 90, 0])
                    cylinder(r = 9, h = 12, center = true, $fn = 32);
            // 螺纹套
            translate([0, 0, -R_OUT + 4]) rotate([0, 90, 0])
                cylinder(r = 9, h = 30, center = true, $fn = 32);
        }
        // M8 螺纹底孔（打印后攻丝 / 热熔铜螺母）
        translate([0, 0, -R_OUT + 4]) rotate([0, 90, 0])
            cylinder(r = 3.4, h = 60, center = true, $fn = 32);
    }
    // 撑脚杆 + TPU 垫（示意）
    translate([26, 0, -R_OUT + 4]) rotate([0, 90, 0])
        cylinder(r = 4, h = FOOT_TRAVEL + 20, center = true, $fn = 32);
    translate([26 + FOOT_TRAVEL / 2 + 12, 0, -R_OUT + 4]) rotate([0, 90, 0])
        cylinder(r = FOOT_D / 2, h = 4, center = true, $fn = 48);
}

// ---------------------------------------------------------------------------
// F. 单调节器（装配态，最短长度）
// ---------------------------------------------------------------------------
module unit(preview = true) {
    // 两端夹持端环
    translate([-L_HALF + CLAMP_W / 2, 0, 0]) clamp_ring();
    translate([ L_HALF - CLAMP_W / 2, 0, 0]) clamp_ring();
    // 外管两半（占满两夹持环之间的全长）
    barrel_half(L_MIN - 2 * CLAMP_W);
    translate([0, 0, 0]) rotate([0, 0, 180]) barrel_half(L_MIN - 2 * CLAMP_W);
    // 内管（缩回态，整根藏在外管里）
    sleeve((L_MIN - 2 * CLAMP_W) * 0.55);
    // 丝杆 + 螺母（示意，长度 = 行程 + 34）
    cyl_x(4, STROKE + 34, 0, 0, -SCREW_OFF);
    // 端头
    translate([ L_HALF + 6.5, 0, 0]) end_head("R");
    translate([-L_HALF - 6.5, 0, 0]) end_head("L");
    // 两端的锥面套筒 + 弹性夹头环（示意，装配态）
    translate([-L_HALF + CLAMP_W / 2, 0, 0]) cone_sleeve();
    translate([ L_HALF - CLAMP_W / 2, 0, 0]) cone_sleeve();
    translate([-L_HALF + 4, 0, 0]) collet_ring();
    translate([ L_HALF - 4, 0, 0]) collet_ring();
    // 顶墙撑脚
    if (preview && (UNIT == "E" || WALL_FOOT)) {
        translate([-L_HALF + 4, 0, 0]) wall_foot();
        translate([ L_HALF - 4, 0, 0]) wall_foot();
    }
}

// ---------------------------------------------------------------------------
// G. 整链预览（墙—调节器—衣—…—墙，K=4 → 5 个调节器）
// ---------------------------------------------------------------------------
module chain_preview(n = 5) {
    pitch = L_MIN + SEAM;               // 一个调节器 + 一个接缝
    x0    = -180;                       // 第 0 个调节器左端
    // 杆
    cyl_x(R_ROD, 1250, 80, 0, 0);
    // 调节器：位置用表达式算，不在 for 里累加（OpenSCAD 的 for 不跨迭代保持变量）
    for (i = [0 : n - 1]) {
        translate([x0 + i * pitch + L_MIN / 2, 0, 0]) unit(true);
    }
    // 衣架钩环（示意：内 R20，跨销桥；真件平面垂直于杆）
    for (i = [1 : n - 1]) {
        translate([x0 + i * pitch - SEAM / 2, 0, -HOOK_DROP])
            rotate([90, 0, 0]) difference() {
                cylinder(r = 21.8, h = 3.6, center = true, $fn = 48);
                cylinder(r = 20, h = 4, center = true, $fn = 48);
                translate([0, -30, 0]) cube([30, 40, 5], center = true);  // 喉口
            }
    }
}

// ---------------------------------------------------------------------------
// H. 打印排版（一台 256×256 的机器一盘装满一个中间段）
// ---------------------------------------------------------------------------
module print_layout() {
    translate([-90, -90, 0]) rotate([0, 0, 90])  clamp_half();
    translate([ 40, -90, 0]) rotate([0, 0, 90])  clamp_half();
    translate([-100, 20, 0]) rotate([0, 0, 0])   end_head("L");
    translate([ 60, 20, 0]) rotate([0, 0, 0])    end_head("R");
    translate([-100, 110, 0]) rotate([0, 0, 0])  cone_sleeve();
    translate([ 0, 110, 0]) rotate([0, 0, 0])    collet_ring();
    translate([110, 110, 0]) rotate([0, 0, 0])   collet_ring();
    translate([-100, 170, 0]) rotate([0, 0, 0])  push_knob();
    translate([-20, 170, 0]) rotate([0, 0, 0])   push_knob();
}

// ---------------------------------------------------------------------------
// 分发
// ---------------------------------------------------------------------------
if (PART == "assembly")      chain_preview();
else if (PART == "clamp_half")   clamp_half();
else if (PART == "clamp_ring")   clamp_ring();
else if (PART == "cone_sleeve")  cone_sleeve();
else if (PART == "collet_ring")  collet_ring();
else if (PART == "push_knob")    push_knob();
else if (PART == "end_head")     end_head("L");
else if (PART == "barrel_half")  barrel_half(L_MIN * 0.42);
else if (PART == "sleeve")       sleeve(L_MIN * 0.5);
else if (PART == "wall_foot")    wall_foot();
else if (PART == "print_layout") print_layout();
else if (PART == "dimensions")   unit(true);
else assert(false, str("PART 取值无效：", PART,
        "；可选 assembly/clamp_half/clamp_ring/cone_sleeve/collet_ring/push_knob/end_head/barrel_half/sleeve/wall_foot/print_layout/dimensions"));
