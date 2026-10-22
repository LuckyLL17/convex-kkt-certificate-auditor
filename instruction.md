# 凸二次模型的 KKT 证书审计

研究团队把一个带坐标下界的凸二次拟合模型交给审计系统。模型的目标函数为

\[
 f(x)=\tfrac12\lVert Ax-b\rVert_2^2+c^\mathsf{T}x,\qquad x_i\ge l_i.
\]

`src/verify.py` 应提供一个命令行程序：

```bash
python3 src/verify.py --input certificate.json --output report.json
```

它读取一个 UTF-8 JSON 文件，审计候选证书，并在成功处理时写出一份 UTF-8 JSON 报告。请完成或修正现有实现；可以重构 `src/verify.py`，但不要新增第三方运行时依赖。

## 输入契约

顶层对象必须且只能包含以下键：`A`、`b`、`c`、`lower`、`x`、`multipliers`，可选键 `tolerance`。

- `A` 是至少一行、每行长度相同的二维数值数组；其列数记为 `n`。`b` 的长度等于 `A` 的行数，`c`、`lower`、`x` 与 `multipliers` 的长度都等于 `n`。
- 所有数值必须是有限的 JSON 数值；布尔值不是数值。`tolerance` 缺省时为 `1e-8`，提供时必须满足 `1e-12 <= tolerance <= 1e-4`。
- `multipliers[i]` 对应约束 `lower[i] - x[i] <= 0` 的乘子。数组和输入键的顺序不影响其数学含义。

## 审计规则

对结构合法的输入，令 `r=Ax-b`、`g=Aᵀr+c`，并使用无穷范数。证书只有同时满足下列条件时才为 `CERTIFIED`：

1. 原始可行性：`max_i(lower[i]-x[i]) <= tolerance`；
2. 对偶可行性：`max_i(-multipliers[i]) <= tolerance`；
3. 平稳性：`||g-multipliers||∞ <= tolerance`；
4. 互补性：`max_i(abs(multipliers[i]*(x[i]-lower[i]))) <= tolerance`。

否则，输入本身仍合法时必须正常退出并给出 `REJECTED` 报告。报告的 `active_lower` 是所有满足 `abs(x[i]-lower[i]) <= tolerance` 的零起始索引，按升序排列。`objective` 必须是公式 `f(x)` 的数值，`residual_inf` 必须为上述四个违反量的非负最大值；所有报告数值都必须有限。

## 输出与失败语义

结构错误、类型错误、非有限数、尺寸不匹配、无法读取输入或无法写入目标文件均为拒收错误：程序必须以非零状态退出，在标准错误写入以 `E_INPUT:` 或 `E_IO:` 开头的一行消息，且**不得改写已有输出文件**。成功处理（包括 `REJECTED`）退出状态为零，并将仅含 `active_lower`、`objective`、`residual_inf`、`status` 四个键的紧凑 JSON 对象原子写入目标文件，文件以一个换行结束。重复执行相同输入必须得到逐字节相同的报告，目标目录中不得遗留临时文件。
