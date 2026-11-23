# 路演 PPT（HTML 版）

> 10 页、16:9、深色科技风。**双击 `index.html` 即可放映**，不需要装 PowerPoint。
> PDF 版：`衣序-HangFlow-DDC2026.pdf`（10 页，2026-11-23 导出）。

## 怎么用

| 操作 | 效果 |
|---|---|
| `→` / `空格` / 点击右半屏 | 下一页 |
| `←` / 点击左半屏 | 上一页 |
| `F` | 全屏 |
| `P` | 打印 / 另存 PDF |
| 浏览器打开 `?s=5` | 直接跳到第 5 页（调试用） |

另附 **A4 展台卡**：[`衣序-展台卡-A4.pdf`](衣序-展台卡-A4.pdf)（单页，打印后放展台；源文件 `handout.html`）。
另有 **完整方案书**：[`衣序-完整方案书.pdf`](衣序-完整方案书.pdf)（152 页，README + 全部 docs 合并，浅色纸张排版、可打印；源文件 `book.html`，重新生成：`python assets/scripts/build_book.py` 后用 Edge 打印）。

## 内容结构（对应 docs/12 的 10 页结构）

1. 封面：产品概念图 + 一句话
2. 痛点：3–5cm → 10–15cm
3. 方案：套挂单元 / RDK 中枢 / 手机网页
4. 现场演示：手机端截图 + 6 步操作
5. 系统架构：五层图
6. 算法：加权间距 + 指标
7. 硬件：接线图 + 6 个关键数字
8. 成本与商业：¥850 打样 / ¥650 量产 / 三档定价
9. 执行：12 天 + 48 小时甘特图与门禁
10. 结尾：四个理由 + 二维码

## 重新导出 PDF

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu `
  --no-pdf-header-footer --print-to-pdf="deck\衣序-HangFlow-DDC2026.pdf" `
  "file:///E:/D-robotics-ClothesRodHelper/deck/index.html"
```

> Edge 会多导出一页空白页；用 `python -c "import pymupdf; ..."` 删掉，或直接在 PPT 软件里删。

## 替换成真二维码

`assets/screenshots/qr-demo.png` 目前指向 `http://192.168.4.1:8000`（RDK 热点网关）。现场如果 IP 变了，用任意二维码工具重新生成同名文件即可。

## 注意

- 所有图片都是相对路径，**整个 deck 目录要一起拷贝**（或连同仓库一起）。
- 字体用系统字体（微软雅黑/PingFang），没有嵌入字体；拷到没有中文的电脑会变成方块——现场用自己的笔记本。


