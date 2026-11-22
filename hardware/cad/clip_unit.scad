// =============================================================================
//  衣序 HangFlow · 套挂单元 ClipUnit —— 参数化主件（OpenSCAD）
// =============================================================================
//  这份文件干什么：把"套挂单元"的全部机械件用参数算出来，改杆径就能重生成。
//
//  坐标系：原点 = 圆杆轴心线与单元 X 向中点；X 沿杆；Z 向上；Y 垂直于杆。
//    - C 形开口朝 -Y 方向（杆从 -Y 侧滑入）
//    - 驱动轮在杆正上方，两惰轮在杆正下方、沿 X 前后各一（抗俯仰力偶）
//    - 挂衣钩吊板从背舱底往下伸，末端一根**沿 X 的水平销**，销心落在
//      (y = 0, z = -HOOK_DROP)：即杆轴心线的正下方。这是硬约束——见 docs/04 §4.2，
//      挂点一旦在 Y 向偏离杆轴，2kg 衣物就会产生绕杆轴的滚转力矩，
//      而圆柱杆 + 轮式接触只能靠摩擦抗滚转（径向法向力对杆轴力矩为零）。
//
//  用法（没有装 OpenSCAD 也能读）：
//    openscad -D 'PART="top_shell"'    -o top_shell.stl    clip_unit.scad
//    openscad -D 'ROD_D=35'            -o clip_35.stl      clip_unit.scad
//    openscad -D 'PART="print_layout"' -o plate.3mf       clip_unit.scad
//    Customizer 里直接改 ROD_D 即可覆盖 Ø20–Ø35 全范围（其余参数自动跟随）。
//
//  ★ 打印预算（0.4 喷嘴 / 0.2 层高 / 3 壁 / 25% 填充，PETG）：
//      上壳 55 g / 2.9 h   下爪 22 g / 1.3 h   挂钩吊板 14 g / 0.9 h   电池盖 9 g / 0.6 h
//      单件均 < 80 g、< 4 h，无需支撑（所有悬垂 ≤ 45°，孔位为通孔）
//  ★ 关键配合：MR63ZZ 轴承位 Ø6 H7；MR84ZZ 轴承位 Ø8 H7；
//      M3 热熔铜螺母底孔 Ø4.0 × 5.5 深；M4 调节滑槽宽 4.4。
// =============================================================================

/* [杆与夹持 —— 改这一组就能换杆径] */
ROD_D       = 25;     // [20:0.5:35] 目标杆径 (mm)，现场按实际杆量一次
FIT_CLEAR   = 0.5;    // 杆腔单边间隙 (mm)，杆不直/有漆时给 0.5–0.8
MOUTH_OPEN  = 1.0;    // 开口比杆径大出的量 (mm)，方便侧向套入

/* [轮系] */
WHEEL_D     = 28;     // 硅胶驱动轮外径 (mm)
WHEEL_W     = 12;     // 驱动轮宽 (mm)
IDLER_D     = 20;     // 惰轮外径 (mm)
IDLER_W     = 8;      // 惰轮宽 (mm)
IDLER_PITCH = 60;     // 两惰轮轴距，沿 X (mm) —— 抗俯仰力臂
IDLER_TIRE  = 2.0;    // 惰轮 TPU 包胶厚度 (mm)，0 = 硬 POM 直接接触

/* [外形] */
BODY_L      = 96;     // 沿杆方向总长 (mm)
WALL        = 3.0;    // 主壁厚 (mm)
LIP         = 6.0;    // 上唇在 -Y 侧的外伸量 (mm)
BACK_DEPTH  = 26;     // 背舱（电池/电路）Y 向深度 (mm)
TOP_Z       = 42;     // 顶面高度 (mm，相对杆轴心)
BOT_Z       = -36;    // 背舱底面高度 (mm)，抬高是为了给衣架钩环留净空
NACELLE_Y   = 31;     // 电机舱在 -Y 侧的最远点 (mm)

/* [预载弹簧（采购件，不打印）] */
SPRING_OD   = 5.0;    // 弹簧外径 (mm)
SPRING_WIRE = 0.6;    // 线径 (mm)
SPRING_FREE = 15.0;   // 自由长 (mm)
SPRING_PRE  = 8.0;    // 装配压缩量 (mm) —— 决定夹持预载 Fs ≈ 2×1.7×8 = 27 N

/* [装配件] */
M3_HN_D     = 4.0;    // M3 热熔铜螺母底孔 (mm)
M3_HN_H     = 5.6;    // 螺母孔深 (mm)
B63_OD      = 6.0;    // MR63ZZ 外径 (mm)
B63_W       = 2.5;    // MR63ZZ 宽 (mm)
B84_OD      = 8.0;    // MR84ZZ 外径 (mm)
B84_W       = 3.0;    // MR84ZZ 宽 (mm)
M4_SLOT_W   = 4.4;    // M4 调节滑槽宽 (mm)
HOOK_DROP   = 48;     // 挂点高度：杆轴心到钩销中心 (mm)。lead 建议 35–45；
                      // 取 48 是为了给标准衣架钩（Ø4 钢丝、环内径 ~Ø16）留 ≥9mm
                      // 竖直净空，否则钩环顶会顶到下爪底面。细衣架可改 44。
HOOK_PIN_D  = 6.0;    // 钩销直径 (mm)，衣架钩环可套
HOOK_PIN_L  = 40;     // 钩销长度 (mm)

/* [显示 / 输出] */
PART      = "all";    // [all, top_shell, lower_jaw, hook, battery_cover, wheel, print_layout]
SHOW_ROD  = true;     // 装配视图里显示参考圆杆
$fn = 48;

// =============================================================================
//  派生参数（不要手改，改上面）
// =============================================================================
ROD_R   = ROD_D / 2;
WHEEL_R = WHEEL_D / 2;
IDLER_R = IDLER_D / 2;
CAV_R   = ROD_R + FIT_CLEAR;              // 杆腔半径
WHEEL_Z = ROD_R + WHEEL_R;                // 驱动轮轴心 Z（轮最低点正好落在杆顶）
IDLER_Z = -(ROD_R + IDLER_R);             // 惰轮轴心 Z（轮最高点正好落在杆底）
BACK_Y0 = CAV_R + WALL;                   // 背舱内壁 Y
BACK_Y1 = BACK_Y0 + BACK_DEPTH - WALL;    // 背舱外壁 Y
FRONT_Y = -(CAV_R + LIP);                 // 上唇外沿 Y
JAW_BOT = IDLER_Z - 10;                   // 下爪横梁底面 Z

assert(ROD_D >= 20 && ROD_D <= 35, "ROD_D 超出设计范围 Ø20–Ø35");
assert(WHEEL_Z + WHEEL_R + 3 <= TOP_Z, "驱动轮顶到上壳顶面了，提高 TOP_Z");
assert(IDLER_PITCH / 2 + IDLER_R + 4 <= BODY_L / 2, "惰轮超出壳长，加大 BODY_L");
assert(BACK_DEPTH - WALL >= 20, "背舱放不下 18650（Ø18.4）");
assert(HOOK_DROP >= -(JAW_BOT) + 10, "挂点离下爪底面太近，衣架钩环会干涉；加大 HOOK_DROP");

echo(str("杆腔直径 = ", 2 * CAV_R, " mm"));
echo(str("驱动轮轴心 Z = ", WHEEL_Z, " mm；惰轮轴心 Z = ", IDLER_Z, " mm"));
echo(str("单元外形 = ", BODY_L, " × ", NACELLE_Y + BACK_Y1, " × ", TOP_Z - HOOK_DROP - 3, " mm（含钩）"));
echo(str("预载估算 Fs ≈ ", 2 * 1.7 * SPRING_PRE, " N（单根 k≈1.7 N/mm，2 根）"));
echo(str("挂点 = (0, 0, ", -HOOK_DROP, ")，Y 向偏移设计值 0 mm"));

// =============================================================================
//  参考件
// =============================================================================
module rod_ref() {
    color([0.75, 0.78, 0.82, 0.55])
        translate([-BODY_L, 0, 0]) rotate([0, 90, 0])
            cylinder(h = 2 * BODY_L, r = ROD_R, center = false);
}

module drive_wheel() {
    // Ø28 硅胶轮（Shore A 50–60），内嵌 2×MR63ZZ，轴为 N20 的 Ø3 D 轴
    color([0.15, 0.15, 0.16])
        translate([0, 0, WHEEL_Z]) rotate([90, 0, 0]) {
            difference() {
                cylinder(h = WHEEL_W, r = WHEEL_R, center = true);
                translate([0, 0, WHEEL_W / 2 - B63_W]) cylinder(h = B63_W + 0.01, r = B63_OD / 2, center = true);
                translate([0, 0, -(WHEEL_W / 2 - B63_W)]) cylinder(h = B63_W + 0.01, r = B63_OD / 2, center = true);
                cylinder(h = WHEEL_W + 2, r = 1.5, center = true);           // Ø3 轴孔
                translate([0, 0, WHEEL_W / 2 - 1.0]) cylinder(h = 1.2, r = 1.55, center = true); // Ø3 磁铁
            }
        }
}

module idler_one(x = 0) {
    // Ø20 惰轮：POM 芯 + TPU 85A 包胶（避免硬塑料在杆面压出亮痕），内嵌 MR84ZZ ×2
    color([0.25, 0.25, 0.28])
        translate([x, 0, IDLER_Z]) rotate([90, 0, 0]) {
            difference() {
                union() {
                    cylinder(h = IDLER_W, r = IDLER_R - IDLER_TIRE, center = true);
                    if (IDLER_TIRE > 0)
                        color([0.55, 0.55, 0.58])
                            cylinder(h = IDLER_W + 1.0, r = IDLER_R, center = true);
                }
                translate([0, 0, IDLER_W / 2 - B84_W]) cylinder(h = B84_W + 0.01, r = B84_OD / 2, center = true);
                translate([0, 0, -(IDLER_W / 2 - B84_W)]) cylinder(h = B84_W + 0.01, r = B84_OD / 2, center = true);
                cylinder(h = IDLER_W + 3, r = 2.05, center = true);          // Ø4 轴过孔
            }
        }
}

// =============================================================================
//  上壳：Γ 形（顶桥 + 背舱），刚性主件，承载驱动轮、电机、电路、电池、挂钩吊板
// =============================================================================
module top_shell() {
    difference() {
        union() {
            // ---- 顶桥：覆盖杆上方 ----
            translate([-BODY_L / 2, FRONT_Y, CAV_R])
                cube([BODY_L, (BACK_Y1 - FRONT_Y), TOP_Z - CAV_R]);
            // ---- 电机舱：-Y 侧上方，装 N20（轴沿 Y，直驱 Ø28 轮）----
            translate([-BODY_L / 2, -NACELLE_Y, CAV_R + 4])
                cube([BODY_L, (NACELLE_Y - CAV_R - 4) + 2, TOP_Z - CAV_R - 4]);
            // ---- 背舱（电池 + 电路）----
            translate([-BODY_L / 2, BACK_Y0, BOT_Z])
                cube([BODY_L, BACK_DEPTH - WALL, TOP_Z - BOT_Z]);
            // ---- 下爪导柱座（背舱 -X 侧壁）----
            for (sx = [-1, 1])
                translate([sx * (BODY_L / 2 - 8) - 12, BACK_Y0 - 2, IDLER_Z - 14])
                    cube([12, 8, 34]);
            // ---- 挂钩吊板根部（背舱底面，2×M3 热熔螺母）----
            translate([-24, BACK_Y0 + 2, BOT_Z - 4]) cube([48, 20, 5]);
            // ---- M3 热熔螺母柱（顶桥 4 处）----
            for (sx = [-1, 1], sy = [FRONT_Y + 6, BACK_Y1 - 6])
                translate([sx * (BODY_L / 2 - 9) - 4.5, sy - 4.5, TOP_Z - WALL])
                    cylinder(h = WALL + 0.01, r = 4.5);
        }

        // ---- 杆腔：圆柱 + 朝 -Y 的开口 ----
        translate([-BODY_L, 0, 0]) rotate([0, 90, 0]) cylinder(h = 2 * BODY_L, r = CAV_R);
        translate([-BODY_L, -(CAV_R + 40), -CAV_R]) cube([2 * BODY_L, CAV_R + 40, 2 * CAV_R]);

        // ---- 驱动轮槽：X∈[-R-2, R+2]，Z∈[CAV_R-0.5, TOP_Z+1]，Y 向贯穿轮宽 ----
        translate([-(WHEEL_R + 2), -(WHEEL_W / 2 + 3), CAV_R - 0.5])
            cube([2 * (WHEEL_R + 2), WHEEL_W + 6, TOP_Z - CAV_R + 2]);
        translate([-BODY_L, -(WHEEL_W / 2 + 2), WHEEL_Z - 2])
            cube([2 * BODY_L, WHEEL_W + 4, 4]);

        // ---- 电机座：N20 12×10×24，轴沿 -Y 出 ----
        translate([-6, -(NACELLE_Y - 4), WHEEL_Z - 6]) cube([12, 20, 10]);
        translate([-3, -NACELLE_Y - 1, WHEEL_Z - 4]) cube([6, 6, 6]);        // 出线槽

        // ---- 电池仓：18650 横放（沿 X），Ø18.4×65 ----
        translate([-34, BACK_Y0 + 1.5, BOT_Z + 3]) cube([68, 20, 21]);

        // ---- M3 螺母孔（顶桥）----
        for (sx = [-1, 1], sy = [FRONT_Y + 6, BACK_Y1 - 6])
            translate([sx * (BODY_L / 2 - 9) - 0.5, sy - 0.5, TOP_Z - WALL - 0.1])
                cylinder(h = 5.7, r = M3_HN_D / 2);

        // ---- 下爪滑槽：两条竖槽，行程 15 mm（覆盖 Ø20→Ø35）----
        for (sx = [-1, 1])
            translate([sx * (BODY_L / 2 - 8) - 3, BACK_Y0 - 3.5, IDLER_Z - 10])
                hull() {
                    cube([6, M4_SLOT_W, 4]);
                    translate([0, 0, 15]) cube([6, M4_SLOT_W, 4]);
                }

        // ---- 挂钩吊板紧固孔（2×M3）----
        for (sx = [-1, 1])
            translate([sx * 16 - 1.6, BACK_Y0 + 4, BOT_Z - 5])
                cylinder(h = 10, r = 1.6);

        // ---- 排水孔（阳台防水：底部不能存水）----
        for (sx = [-2 : 2])
            translate([sx * 18, BACK_Y0 + 8, BOT_Z - 0.1]) cylinder(h = 1.0, r = 1.5);
    }
}

// =============================================================================
//  下爪：托住两个惰轮，弹簧上顶压在杆底面；两条 M4 滑槽决定杆径档位
// =============================================================================
module lower_jaw() {
    difference() {
        union() {
            // 横梁
            translate([-BODY_L / 2 + 6, -CAV_R + 2, JAW_BOT])
                cube([BODY_L - 12, BACK_Y0 + CAV_R, 8]);
            // 两侧惰轮支臂
            for (sx = [-1, 1])
                translate([sx * IDLER_PITCH / 2 - 7, -IDLER_W / 2 - 4, IDLER_Z - 7])
                    cube([14, IDLER_W + 8, 14]);
            // 导柱耳（插进上壳滑槽）
            for (sx = [-1, 1])
                translate([sx * (BODY_L / 2 - 8) - 6, BACK_Y0 - 3, IDLER_Z - 12])
                    cube([12, 5, 16]);
            // 弹簧座（两处，朝上）
            for (sx = [-1, 1])
                translate([sx * 26 - 4, BACK_Y0 - 12, JAW_BOT])
                    cylinder(h = 10, r = SPRING_OD / 2 + 1.2);
        }
        // 惰轮轴孔 Ø4（H7）
        for (sx = [-1, 1])
            translate([sx * IDLER_PITCH / 2, 0, IDLER_Z]) rotate([90, 0, 0])
                cylinder(h = 40, r = 2.0, center = true);
        // 让杆腔
        translate([-BODY_L, 0, 0]) rotate([0, 90, 0]) cylinder(h = 2 * BODY_L, r = CAV_R + 1);
        // M4 滑槽螺钉孔
        for (sx = [-1, 1])
            translate([sx * (BODY_L / 2 - 8), BACK_Y0 - 0.5, IDLER_Z + 0.5]) rotate([90, 0, 0])
                cylinder(h = 12, r = 2.2, center = true);
        // 弹簧腔
        for (sx = [-1, 1])
            translate([sx * 26 - 4, BACK_Y0 - 12, JAW_BOT + 1])
                cylinder(h = 12, r = SPRING_OD / 2 + 0.3);
    }
}

// =============================================================================
//  挂衣钩吊板：背舱底面 → 往下 → 穿过两块侧吊板的 Ø6 不锈钢销
//  销心 (0, 0, -HOOK_DROP)：即杆轴心线的正下方；两吊板放在 |x| = 19，
//  让出衣架钩环（|x| ≤ 4）的通道。销子是采购件（Ø6 不锈钢圆销），
//  不打印——打印件沿层方向受弯很弱。
// =============================================================================
module hook() {
    z_bot   = -HOOK_DROP - 2;          // 侧吊板底（略低于销心）
    z_join  = BOT_Z - 4;               // 侧吊板顶 / 与根部搭接
    difference() {
        union() {
            // 与背舱底面贴合的根部（2×M3 热熔螺母）
            translate([-24, BACK_Y0 + 2, BOT_Z - 5]) cube([48, 20, 5]);
            // 两块侧吊板：从根部往下抱到销子两端（|x|=19，让出衣架钩环）
            for (sx = [-1, 1])
                translate([sx * 19 - 3, -4, z_bot])
                    cube([6, 22, z_join - z_bot]);
            // 根部与侧吊板之间的过渡块
            translate([-22, -4, z_join - 1]) cube([44, 16, 5]);
            // 钩尖防滑唇（-Y 侧微翘，防衣架被风甩出）
            translate([-21, -10, -HOOK_DROP - 5]) cube([42, 4, 7]);
        }
        // 销孔 Ø6.2，沿 X 贯穿两吊板（不锈钢销穿过去）
        translate([-24, 0, -HOOK_DROP]) rotate([0, 90, 0]) cylinder(h = 48, r = 3.1, center = true);
        // M3 沉头孔
        for (sx = [-1, 1])
            translate([sx * 16, BACK_Y0 + 12, BOT_Z - 6]) cylinder(h = 8, r = 1.7);
        // 减重槽（保留吊板受力断面）
        for (sx = [-1, 1])
            translate([sx * 19 - 1.5, 2, z_bot + 2]) cube([3, 8, 3]);
    }
}

module steel_pin() {
    // 采购件：Ø6 不锈钢圆销 ×40，衣架钩挂在这里
    color([0.68, 0.70, 0.74])
        translate([-HOOK_PIN_L / 2, 0, -HOOK_DROP]) rotate([0, 90, 0])
            cylinder(h = HOOK_PIN_L, r = HOOK_PIN_D / 2);
}

// =============================================================================
//  电池仓盖（TPU 95A 密封圈压紧面）
// =============================================================================
module battery_cover() {
    difference() {
        translate([-34, BACK_Y0 - 1, BOT_Z - 1]) cube([68, 24, 4]);
        translate([-31, BACK_Y0 + 2, BOT_Z]) cube([62, 18, 2]);              // 减重
        for (sx = [-1, 1])
            translate([sx * 30, BACK_Y0 + 10, BOT_Z - 2]) cylinder(h = 8, r = 1.7);
        // 密封圈槽 1.5×1.2（TPU 95A O 形圈）
        translate([-32, BACK_Y0, BOT_Z + 3.2])
            difference() {
                cube([64, 21, 1.4]);
                translate([1.2, 1.2, -0.1]) cube([61.6, 18.6, 1.6]);
            }
    }
}

// =============================================================================
//  打印排版（一板打完，估 5.7 h / 100 g）
// =============================================================================
module print_layout() {
    translate([0, 0, 0]) top_shell();
    translate([0, 105, 0]) lower_jaw();
    translate([20, 150, 0]) rotate([90, 0, 0]) hook();
    translate([110, 150, 0]) battery_cover();
}

// =============================================================================
//  输出
// =============================================================================
module assembly() {
    top_shell();
    lower_jaw();
    hook();
    steel_pin();
    battery_cover();
    drive_wheel();
    idler_one(-IDLER_PITCH / 2);
    idler_one(+IDLER_PITCH / 2);
    if (SHOW_ROD) rod_ref();
}

if (PART == "all")                 assembly();
else if (PART == "top_shell")      top_shell();
else if (PART == "lower_jaw")      lower_jaw();
else if (PART == "hook")           hook();
else if (PART == "battery_cover")  battery_cover();
else if (PART == "wheel")          drive_wheel();
else if (PART == "print_layout")   print_layout();
else echo(str("未知 PART: ", PART, "（可选 all/top_shell/lower_jaw/hook/battery_cover/wheel/print_layout）"));
