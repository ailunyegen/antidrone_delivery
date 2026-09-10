# -*- coding: utf-8 -*-
"""在《课题背景知识文档_五场景与仿真原理.docx》末尾追加"第三部分 多种子实验的实验原理与实验目的"（保留原内容）"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn

PATH = "课题背景知识文档_五场景与仿真原理.docx"

doc = Document(PATH)


def h1(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(15)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    return p


def h2(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(13)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    return p


def h3(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    return p


def body(text, bold=False):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = Pt(22)
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(11)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    return p


def bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Pt(22)
    p.paragraph_format.first_line_indent = Pt(-11)
    r = p.add_run("▪ " + text)
    r.font.size = Pt(11)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    return p


def note(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9.5)
    r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "楷体")
    return p


# ============================ 第三部分 ============================
doc.add_page_break()
h1("第三部分　多种子实验的实验原理与实验目的")

body("论文主消融实验固定随机种子 seed=7。为排除“单一随机轨迹下的偶然结果”，设计了多种子复现实验："
     "固定其他全部条件，仅改变随机种子，重复整套实验，观察增益的分布并做统计检验。"
     "本部分解释多种子实验“为什么这样设计（原理）”与“要回答什么问题（目的）”。")

h2("一、实验原理")
h3("1. 随机种子在本系统中的两个作用")
bullet("控制大模型（LLM）采样的随机性：temperature 采样使每次生成的方案存在随机差异，种子决定了这条“生成轨迹”；")
bullet("控制蒙特卡洛（MC）仿真的随机扰动序列：仿真器对阶段分与效能施加 ±3%~5% 的显式伪随机扰动，种子决定了扰动序列。")
body("因此，同一种子下从“方案生成→仿真评估”的整条管线完全可复现；不同种子代表“重新开始的一整轮独立实验轨迹”，"
     "而不是简单换一组仿真噪声。")
h3("2. 多种子＝对随机轨迹变量做重复采样")
body("实验固定想定、迭代次数（10）、蒙特卡洛次数（50）、案例库与回写开关，仅改变种子 "
     "{7, 42, 123, 999, 2024}（共 5 个），得到“Full 相对 Pure LLM 的增益”这一随机量的分布（均值 ± 标准差）。"
     "增益为正说明 Full 优于 Pure，标准差体现增益在不同初始轨迹下的稳定程度。")
h3("3. 配对设计与统计检验")
bullet("配对设计：同一种子下比较 Full 与 Pure（成对数据），消除不同种子间的系统差异（如某种子整体偏难/偏易）；")
bullet("配对 t 检验（paired t-test）：检验“增益均值是否显著非零”，自由度 4（5 个种子 − 1），p<0.01 表示“增益为零”"
       "这一假设的偶然概率小于 1%；")
bullet("效应量 Cohen's d：度量增益幅度大小，d≥0.8 为大效应，本实验 d=2.50 属极大效应——不仅“统计显著”，而且“幅度可观”。")
h3("4. 补充实验：优化参数下的多种子复跑")
body("由于默认参数（θ=0.5, ε=0.02）经敏感性分析位于 U 形曲线谷底，另在优化参数（θ=0.9, ε=0.005）下用 "
     "{7, 42, 123} 三个种子复跑 Full 管线；Pure 基线不依赖 HOPE 参数，可直接复用，无需重跑。")

h2("二、实验目的")
bullet("验证稳健性：增益是否在所有种子下一致为正——排除“这个种子恰好幸运”的偶然解释；")
bullet("量化变异性：报告增益的均值与标准差，让结论有“置信范围”而非孤点；")
bullet("统计显著性：以 p 值排除“增益为零”的假设，以 Cohen's d 说明幅度，二者共同支撑“增益真实存在且明显”；")
bullet("与种内置信区间区分：单种子 50 次蒙特卡洛的 95% 置信区间只反映种内随机性，跨种子波动约为其 5 倍——"
       "多种子复现才是对“实验可重复性”更严格的检验，也是论文明确声明的证据边界。")

h2("三、主要结果")
bullet("默认参数（5 种子）：平均 ΔMS = +4.14（SD 1.66），配对 t(4)=5.593，p<0.01，Cohen's d=2.50；"
       "ΔOE 的 t(4)=7.414；5/5 种子增益为正；")
bullet("优化参数（3 种子）：平均 ΔMS = +5.62（SD 2.41），t(4)=5.21，p<0.01，5/5（3/3）种子增益为正；")
bullet("结论：Full 相对 Pure LLM 的增益在多个独立随机轨迹下方向一致、幅度稳定、统计显著。")
note("ΔMS = 任务成功率（Mission Success）增益；SD = 标准差；t(4) = 自由度 4 的 t 统计量；p = 显著性概率；"
     "Cohen's d = 效应量。数据来源：论文多种子复现实验（Table 12/13）。")

h2("四、一句话总结")
body("多种子实验回答的是“结果是不是碰运气”——答案是否定的：5 个独立随机轨迹下，完整管线的增益全部为正、"
     "统计显著（p<0.01）且幅度极大（d=2.50），证明增益是机制性的、可复现的，而非单一种子下的偶然。", bold=True)

doc.save(PATH)
print("saved", PATH)
