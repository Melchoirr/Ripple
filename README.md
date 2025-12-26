# Ripple - 原生响应式流语言

<div align="center">

**从语言层面解决状态管理问题的响应式编程语言**

[快速开始](QUICKSTART.md) | [错误处理](ERROR_HANDLING.md) | [示例代码](examples/)

</div>

---

## 概述

Ripple 是一种实验性的响应式编程语言，旨在从语言层面解决传统命令式编程中的状态管理复杂性。它的核心理念是：**变量不是存储数据的静态容器，而是随时间变化的数据流（Stream）**。

### 核心特性

- **🔄 原生响应式**: 依赖图作为运行时的一等公民，自动追踪数据流
- **⚡ 零故障传播**: 基于拓扑排序的严格执行顺序，保证状态一致性
- **🕐 隐式时间轴**: 无需显式订阅/取消订阅，时间被抽象为流的自然属性
- **📊 声明式语法**: 类似电子表格的直观编程模型
- **⚠️ 完整错误检测**: 编译期捕获循环依赖、未定义引用、重复定义等错误
- **🔍 类型推断**: 自动推断变量类型，减少冗余注解
- **📁 CSV 数据处理**: 内置 CSV 文件加载与统计函数
- **👁️ 文件监听**: 自动监听 CSV 文件变化，实时更新计算结果
- **🌳 AST 可视化**: 支持树形、DOT、JSON 多种格式输出

---

## 快速开始

### 运行演示

```bash
# 完整功能演示
python demo.py

# 运行测试套件
python test_error_handling.py

# 交互式运行示例
python ripple_runner.py examples/example1_diamond.rpl
```

### 第一个程序

创建文件 `hello.rpl`:

```ripple
// 声明输入源
source A : int := 1;

// 声明计算流
stream B <- A * 2;
stream C <- A + 1;
stream D <- B + C;

// 输出结果
sink output <- D;
```

运行程序：

```bash
python ripple_runner.py hello.rpl
```

在交互模式中输入：

```
> A = 5
```

你会看到输出：

```
推送事件: A = 5

当前输出：
  output = 16
```

这展示了 Ripple 的核心特性：当 `A` 变为 5 时，`B` 自动更新为 10，`C` 自动更新为 6，`D` 自动计算为 16，**并且只计算一次**，不会出现中间错误状态。

### 交互模式命令

| 命令 | 说明 |
|------|------|
| `source = value` | 向源节点推送值 |
| `graph` | 显示依赖图结构 |
| `outputs` | 显示当前所有输出 |
| `sources` | 列出所有源节点 |
| `watch` | 开启/关闭 CSV 文件监听 |
| `ast` | 显示 AST（树形） |
| `ast dot` | 显示 AST（DOT 格式）并保存 |
| `ast json` | 显示 AST（JSON 格式） |
| `help` | 显示帮助 |
| `quit` | 退出程序 |

---

## 语言特性

### 1. 基本语法

#### 源声明（Source）

```ripple
source temperature : float := 20.0;
source enabled : bool := true;
```

#### 流声明（Stream）

```ripple
stream celsius <- temperature;
stream fahrenheit <- celsius * 9.0 / 5.0 + 32.0;
stream is_hot <- fahrenheit > 86.0;
```

#### 输出节点（Sink）

```ripple
sink temp_output <- fahrenheit;
sink alert <- is_hot;
```

### 2. 条件表达式

```ripple
stream status <- if temperature < 10.0 then "cold"
                 else if temperature < 25.0 then "comfortable"
                 else "hot" end end;
```

### 3. 时序操作符

#### Pre - 访问历史值

```ripple
source tick : int := 0;
stream counter <- pre(counter, 0) + 1;
```

#### Fold - 状态累积

```ripple
source numbers : int := 0;
stream sum <- fold(numbers, 0, (acc, x) => acc + x);
```

### 4. CSV 数据处理

Ripple 内置了 CSV 文件处理功能，支持加载、查询和统计。

#### 加载 CSV 文件

```ripple
// 加载 CSV，第二个参数表示是否跳过表头
source data := load_csv("data/employees.csv", true);

// 获取表头
stream headers <- csv_header("data/employees.csv");
```

#### 数据访问

```ripple
// 获取指定列（0-indexed）
stream ages <- col(data, 1);       // 第2列
stream names <- col(data, 0);      // 第1列

// 获取指定行
stream first_row <- row(data, 0);  // 第1行
```

#### 统计函数

```ripple
// 基础统计
stream row_count <- len(data);           // 行数
stream avg_age <- avg(col(data, 1));     // 平均值
stream total <- sum(col(data, 2));       // 求和
stream max_val <- max(col(data, 2));     // 最大值
stream min_val <- min(col(data, 2));     // 最小值

// 条件统计
stream active_count <- count_if(data, (row) => row[3] == true);
stream high_salary <- count_if(data, (row) => row[2] > 5000);
```

#### 数据过滤

```ripple
// 过滤满足条件的行
stream active_users <- filter(data, (row) => row[3] == true);
stream seniors <- filter(data, (row) => row[1] > 30);
```

#### 完整示例

```ripple
// 员工数据分析
source employees := load_csv("data/employees.csv", true);

stream total_employees <- len(employees);
stream avg_salary <- avg(col(employees, 2));
stream active_employees <- filter(employees, (row) => row[3]);
stream active_count <- len(active_employees);

sink report_total <- total_employees;
sink report_avg_salary <- avg_salary;
sink report_active <- active_count;
```

### 5. 文件监听（实时更新）

在交互模式下，可以启用 CSV 文件监听，当文件内容变化时自动更新计算结果：

```bash
python ripple_runner.py examples/example9_csv.rpl
```

```
> watch
[文件监听] 已启动，监听 1 个文件

# 此时修改 CSV 文件并保存，输出会自动更新：
[文件监听] 检测到 'data/employees.csv' 变化，重新加载...
  加载了 10 行数据

当前输出：
  report_total = 10
  report_avg_salary = 5500.0
```

支持同时监听多个 CSV 文件：

```ripple
source users := load_csv("data/users.csv", true);
source orders := load_csv("data/orders.csv", true);
source products := load_csv("data/products.csv", true);

// 所有文件都会被自动监听
```

### 6. AST 可视化

Ripple 支持三种 AST 可视化格式：

#### 命令行模式

```bash
# 树形格式
python ripple_runner.py examples/example1_diamond.rpl --ast tree

# Graphviz DOT 格式
python ripple_runner.py examples/example1_diamond.rpl --ast dot

# JSON 格式
python ripple_runner.py examples/example1_diamond.rpl --ast json
```

#### 交互模式

```
> ast           # 显示树形 AST
> ast tree      # 显示树形 AST
> ast dot       # 显示 DOT 格式并保存文件
> ast json      # 显示 JSON 格式
```

#### DOT 文件转换

生成的 `.dot` 文件可以用 Graphviz 转换为图片：

```bash
# 安装 Graphviz
brew install graphviz

# 转换为 PNG
dot -Tpng example_ast.dot -o example_ast.png

# 转换为 SVG
dot -Tsvg example_ast.dot -o example_ast.svg
```

或使用在线工具：https://dreampuf.github.io/GraphvizOnline/

---

## 错误处理

Ripple 提供完整的编译期错误检测：

### 循环依赖检测

❌ **错误代码：**
```ripple
stream A <- B + 1;
stream B <- C + 1;
stream C <- A + 1;  // 循环依赖
```

**错误信息：**
```
Error: Circular dependency detected: A -> B -> C -> A
```

### 未定义引用检测

❌ **错误代码：**
```ripple
source A : int := 1;
stream B <- A + X;  // X 未定义
```

**错误信息：**
```
Error: Undefined reference 'X' in 'B'
```

### 重复定义检测

❌ **错误代码：**
```ripple
source A : int := 1;
stream B <- A * 2;
stream B <- A + 1;  // 重复定义
```

**错误信息：**
```
Error: Duplicate definition of 'B'
```

详细的错误处理指南请查看 [ERROR_HANDLING.md](ERROR_HANDLING.md)

---

## 项目结构

```
adsl/
├── ripple_lexer.py          # 词法分析器
├── ripple_ast.py            # AST 节点定义
├── ripple_parser.py         # 语法分析器
├── ripple_engine.py         # 图归约引擎 + CSV 处理
├── ripple_compiler.py       # 编译器（带错误检测 + 类型推断）
├── ripple_typechecker.py    # 类型推断系统
├── ripple_errors.py         # 错误处理系统
├── ripple_runner.py         # 交互式运行器
├── ripple_ast_visualizer.py # AST 可视化器
├── ripple_watcher.py        # CSV 文件监听器
├── demo.py                  # 演示程序
├── test_error_handling.py   # 测试套件
│
├── examples/                # 示例代码
│   ├── example1_diamond.rpl     # 菱形依赖
│   ├── example2_counter.rpl     # 计数器
│   ├── example3_fold.rpl        # 折叠操作
│   ├── example4_conditional.rpl # 条件表达式
│   ├── example5_complex.rpl     # 复杂示例
│   ├── example9_csv.rpl         # CSV 数据处理
│   ├── test_data.csv            # 测试 CSV 数据
│   └── error_examples.rpl       # 错误示例
│
└── 文档
    ├── README.md            # 本文件
    ├── QUICKSTART.md        # 快速入门
    └── ERROR_HANDLING.md    # 错误处理指南
```

---

## 核心算法：零故障传播

### 理论保证

**定理**：Ripple 保证每个节点在每次传播中只计算一次。

**证明**：
1. 定义 `rank(n) = 1 + max(rank(d) for d in dependencies(n))`
2. 源节点 `rank = 0`
3. 调度器总是优先处理 rank 最小的节点
4. 归纳证明：
   - Base: rank=0 的源节点由外部驱动，值确定
   - Step: 假设 rank<k 的节点都已稳定
     * 处理 rank=k 的节点 n 时
     * 其依赖的 rank 必然 <k（无环性质）
     * 因此 n 基于稳定输入计算
     * n 只计算一次，结果正确 ✓

### 菱形依赖示例

```
    A (rank=0)
   / \
  /   \
 B     C (rank=1)
  \   /
   \ /
    D (rank=2)
```

当 A 更新时：
1. B 和 C 加入队列（都是 rank=1）
2. 先处理 B（或 C），计算完成
3. 再处理 C（或 B），计算完成
4. D 加入队列（rank=2）
5. D 基于 B 和 C 的**最终值**计算，只计算一次

**验证：**
```
A=1 -> B=2, C=2, D=4
A=2 -> B=4, C=3, D=7  ✓ D 只计算一次！
A=5 -> B=10, C=6, D=16 ✓
```

---

## 编译流程

```
源代码 (.rpl)
    ↓
[1] 词法分析 → Tokens
    ↓
[2] 语法分析 → AST
    ↓
[3] 类型定义编译
    ↓
[4] 函数定义编译
    ↓
[5] 类型推断与检查 🔍
    ↓
[6] 检查重复定义 ⚠️
    ↓
[7] 检查未定义引用 ⚠️
    ↓
[8] 检查循环依赖 ⚠️
    ↓
[9] 计算拓扑顺序
    ↓
[10] 编译源/流/输出节点
    ↓
[11] 初始化依赖图
    ↓
✓ 响应式执行引擎
```

**原则**：早期失败 - 一旦发现错误立即停止编译。

**编译输出**：Ripple 不生成传统的字节码或机器码，而是生成**响应式依赖图**，由运行时引擎执行。

---

## 测试

### 运行测试套件

```bash
python test_error_handling.py
```

**测试统计：**
- 总测试数：15 个
- 通过：15 个 ✓
- 通过率：100% 🎉

**测试覆盖：**
- ✅ 正确代码编译（3个测试）
- ✅ 循环依赖检测（3个测试）
- ✅ 未定义引用检测（3个测试）
- ✅ 重复定义检测（3个测试）
- ✅ 边界情况（3个测试）

---

## 与其他语言/库的对比

| 特性 | Ripple | RxJS | Elm | Excel |
|------|--------|------|-----|-------|
| **响应方式** | 语言特性 | 库/API | 架构 | 环境 |
| **依赖构建** | **隐式** | 显式 | 显式 | 隐式 |
| **故障处理** | **拓扑保证** | 无保证 | 帧更新 | 拓扑 |
| **错误检测** | **编译期** | 运行期 | 编译期 | 运行期 |
| **状态管理** | **自动** | 手动 | Model | 自动 |

### Ripple 的独特优势

- **语言级响应式** - 不是库，是语言特性
- **编译期错误检测** - 在运行前捕获所有循环依赖
- **零样板代码** - 无需 subscribe/unsubscribe
- **数学保证** - 形式化证明的正确性

---

## 示例程序

### 示例 1: 菱形依赖

文件: [examples/example1_diamond.rpl](examples/example1_diamond.rpl)

```ripple
source A : int := 1;
stream B <- A * 2;
stream C <- A + 1;
stream D <- B + C;
sink output <- D;
```

### 示例 2: 温度监控

文件: [examples/example4_conditional.rpl](examples/example4_conditional.rpl)

```ripple
source temperature : float := 20.0;

stream status <- if temperature < 10.0 then "cold"
                 else if temperature < 25.0 then "comfortable"
                 else "hot" end end;

stream action <- if status == "hot" then "Turn on AC"
                 else if status == "cold" then "Turn on heater"
                 else "No action needed" end end;
```

更多示例请查看 [examples/](examples/) 目录。

---

## 文档

- [QUICKSTART.md](QUICKSTART.md) - 5分钟快速入门
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - 错误处理完整指南
- [设计报告](Ripple%20(原生响应式流语言)%20深度设计与实现研究报告.md) - 理论基础

---

## 技术亮点

### 1. 完整性
- ✓ 从词法到运行时的全栈实现
- ✓ 涵盖编译器所有关键阶段

### 2. 正确性
- ✓ 基于数学证明的零故障传播
- ✓ 拓扑排序保证执行顺序

### 3. 健壮性
- ✓ 完善的错误检测（循环/未定义/重复）
- ✓ 详细的错误报告（带源码上下文）
- ✓ 早期失败原则

### 4. 可用性
- ✓ 交互式运行器
- ✓ 6 个示例程序
- ✓ 友好的命令行界面

### 5. 教学性
- ✓ 清晰的代码结构
- ✓ 详细的注释
- ✓ 完整的文档

---

## 已实现特性

- ✅ 类型推断系统
- ✅ 用户自定义函数
- ✅ CSV 数据处理
- ✅ 文件监听与实时更新
- ✅ AST 可视化（树形/DOT/JSON）
- ✅ Lambda 表达式
- ✅ 高阶函数（map, filter, fold）

## 未来工作

根据设计文档，以下特性待实现：

1. **类型系统增强**
   - 泛型支持
   - 更完善的类型错误报告

2. **高级特性**
   - 高阶流（Stream of Streams）
   - Match 表达式（模式匹配）

3. **性能优化**
   - Slab 内存分配器
   - 波前并行执行

4. **工具链**
   - 时间旅行调试器
   - LTL 断言验证
   - IDE 插件（VSCode/IntelliJ）

---

## 许可证

本项目是一个实验性研究项目，基于《Ripple (原生响应式流语言) 深度设计与实现研究报告》实现。

---

**Ripple - 让数据流动起来！** 🌊



## 其他语言的对比

### Lustre（同步数据流语言）



```lustre
counter = 0 -> pre(counter) + 1;
```

`0 ->` 就是初始值语法



### Haskell（scanl）



```haskell
scanl (+) 0 [1,2,3]  -- 0 是初始值
```

### JavaScript（reduce）



```javascript
[1,2,3].reduce((acc, x) => acc + x, 0)  // 0 是初始值
```

------

## 能不能省略初始值？

理论上可以设计默认值：



- `int` 默认 0
- `float` 默认 0.0
- `bool` 默认 false
- `string` 默认 ""

但显式初始值更好，因为：



1. **语义清晰**：读代码就知道从哪开始
2. **避免意外**：有些场景初始值不应该是 0（比如乘法累积应该从 1 开始）
3. **类型安全**：编译器可以推断类型
