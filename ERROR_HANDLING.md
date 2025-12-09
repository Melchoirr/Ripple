# Ripple 语言 - 错误处理指南

## 概述

Ripple 编译器提供了完整的错误检测和报告机制，可以在编译期捕获各种常见错误，帮助开发者快速定位和修复问题。

---

## 错误类型

### 1. 循环依赖错误 (Circular Dependency)

**最常见的错误之一**。当多个流形成循环依赖关系时会触发。

#### 示例

❌ **错误代码：**
```ripple
source A : int := 1;
stream B <- C + 1;  // B 依赖 C
stream C <- D + 1;  // C 依赖 D
stream D <- B + 1;  // D 依赖 B
sink output <- D;
```

**错误信息：**
```
Circular dependency detected: B -> C -> D -> B
```

**说明：**
- B 依赖 C，C 依赖 D，D 又依赖 B，形成了循环
- 编译器会检测出所有的循环路径并报告

✅ **正确写法：**
```ripple
source A : int := 1;
stream B <- A + 1;  // B 依赖源 A
stream C <- B + 1;  // C 依赖 B
stream D <- C + 1;  // D 依赖 C
sink output <- D;
```

#### 特殊情况：使用 Pre 的自引用

✅ **这是允许的：**
```ripple
source tick : int := 0;
stream counter <- pre(counter, 0) + 1;
```

**原因：**
- `pre(counter, 0)` 访问的是**前一时刻**的 counter 值
- 这打破了逻辑上的循环依赖
- 编译器会自动识别并允许这种模式

---

### 2. 未定义引用错误 (Undefined Reference)

当流引用了不存在的变量时会触发。

#### 示例

❌ **错误代码：**
```ripple
source A : int := 1;
stream B <- A * 2;
stream C <- B + X;  // X 未定义
sink output <- C;
```

**错误信息：**
```
Undefined reference 'X' in 'C'
```

✅ **正确写法：**
```ripple
source A : int := 1;
source X : int := 5;  // 先定义 X
stream B <- A * 2;
stream C <- B + X;    // 现在可以使用 X
sink output <- C;
```

**常见原因：**
1. 拼写错误（例如写成 `Coutner` 而不是 `Counter`）
2. 忘记声明源节点
3. 引用顺序问题（Ripple 允许前向引用，但变量必须在某处定义）

---

### 3. 重复定义错误 (Duplicate Definition)

当同一个名字被定义多次时会触发。

#### 示例

❌ **错误代码：**
```ripple
source A : int := 1;
stream B <- A * 2;
stream B <- A + 1;  // B 被重复定义
sink output <- B;
```

**错误信息：**
```
Duplicate definition of 'B'
```

✅ **正确写法：**
```ripple
source A : int := 1;
stream B <- A * 2;
stream C <- A + 1;  // 使用不同的名字
sink output <- B;
sink output2 <- C;
```

**注意：**
- 源节点、流节点、Sink 节点共享同一个命名空间
- 不能有同名的 source 和 stream
- 每个名字只能定义一次

---

### 4. 类型错误 (Type Error)

*（当前版本简化实现，完整类型检查待实现）*

未来版本将支持：
- 类型不匹配检查
- 运算符类型约束
- 函数参数类型验证

---

## 编译流程和错误检查

Ripple 编译器按以下顺序进行错误检查：

```
1. [词法分析]     → 检查 Token 合法性
2. [语法分析]     → 检查语法结构
3. [重复定义检查] → 确保没有重名
4. [未定义引用]   → 确保所有引用都有定义
5. [循环依赖检测] → 确保依赖图无环
6. [拓扑排序]     → 计算执行顺序
7. [代码生成]     → 生成依赖图
```

**早期失败原则：** 一旦发现错误，立即停止编译并报告，不会继续后续阶段。

---

## 使用增强版编译器

### 方法 1: 使用 Python API

```python
from ripple_compiler_v2 import RippleCompilerV2

code = """
source A : int := 1;
stream B <- A * 2;
stream C <- B + X;  // 故意的错误
"""

compiler = RippleCompilerV2()
try:
    engine = compiler.run(code)
except Exception as e:
    print("编译失败：", e)
```

### 方法 2: 命令行工具

```bash
# 使用增强版编译器运行
python ripple_compiler_v2.py
```

---

## 错误报告格式

当发生错误时，编译器会生成详细的错误报告：

```
================================================================================
Compilation failed with 2 error(s):
================================================================================

[1] Error: Undefined reference 'X' in 'C'

Context:
    1 | source A : int := 1;
    2 | stream B <- A * 2;
>>> 3 | stream C <- B + X;
              ^
    4 | sink output <- C;

[2] Error: Circular dependency detected: B -> C -> B

================================================================================
```

**报告包含：**
- 错误数量
- 每个错误的详细描述
- 错误发生的上下文（源代码行）
- 错误位置标记

---

## 调试技巧

### 1. 循环依赖的调试

**步骤：**
1. 找到报告中的循环路径，例如 `A -> B -> C -> A`
2. 画出依赖图：
   ```
   A ──> B
   ↑     │
   │     ↓
   └─── C
   ```
3. 确定哪个依赖是不必要的或错误的
4. 重构代码，打破循环

**常见解决方案：**
- 引入新的源节点
- 使用 `pre` 操作符（如果需要时间延迟）
- 重新设计数据流

### 2. 未定义引用的调试

**步骤：**
1. 检查拼写是否正确
2. 确认变量是否已声明为 `source` 或 `stream`
3. 检查作用域（Ripple 是全局作用域）

**工具：**
```bash
# 列出所有源节点
> sources

# 查看依赖图
> graph
```

### 3. 使用测试文件

查看 [examples/error_examples.rpl](examples/error_examples.rpl) 了解各种错误示例。

---

## 错误处理 API 参考

### 主要类

#### `RippleCompilerV2`

增强版编译器，集成完整错误检查。

```python
compiler = RippleCompilerV2()
engine = compiler.run(source_code)
```

#### `ErrorReporter`

错误收集和报告工具。

```python
reporter = ErrorReporter(source_code)
reporter.add_error(error)
reporter.print_report()
reporter.raise_if_errors()
```

#### `CircularDependencyDetector`

循环依赖检测器。

```python
detector = CircularDependencyDetector()
cycles = detector.find_all_cycles(deps_graph)
```

#### 错误类型

```python
from ripple_errors import (
    CircularDependencyError,
    UndefinedReferenceError,
    DuplicateDefinitionError,
    CompileError,
    RuntimeError
)
```

---

## 最佳实践

### 1. 命名规范

```ripple
// 源节点：使用小写或 camelCase
source temperature : float;
source currentPrice : float;

// 流节点：使用描述性名称
stream temperatureInFahrenheit <- ...;
stream movingAverage <- ...;

// Sink：使用 _output 后缀
sink temp_output <- ...;
sink price_output <- ...;
```

### 2. 避免复杂依赖

❌ **不好：**
```ripple
stream result <- (A + B) * (C + D) * (E + F) * (G + H);
```

✅ **更好：**
```ripple
stream sum1 <- A + B;
stream sum2 <- C + D;
stream sum3 <- E + F;
stream sum4 <- G + H;
stream result <- sum1 * sum2 * sum3 * sum4;
```

**优点：**
- 更易于理解
- 更易于调试
- 更好的可视化

### 3. 模块化设计

将复杂逻辑分解为多个小的流：

```ripple
// 输入处理
source raw_data : float;
stream cleaned_data <- validate(raw_data);

// 特征提取
stream feature1 <- extract_feature_1(cleaned_data);
stream feature2 <- extract_feature_2(cleaned_data);

// 决策逻辑
stream decision <- make_decision(feature1, feature2);

// 输出
sink result <- decision;
```

---

## 常见问题 (FAQ)

### Q1: 为什么 `pre(counter, 0)` 不算循环依赖？

**A:** `pre` 操作符引用的是**前一个时间步**的值，在逻辑上打破了循环。就像：
```
t=0: counter = 0 (初始值)
t=1: counter = pre(counter, 0) + 1 = 0 + 1 = 1
t=2: counter = pre(counter, 0) + 1 = 1 + 1 = 2
```

每个时刻的计算都基于**已知的**历史值，不是循环。

### Q2: 可以前向引用吗？

**A:** 可以！Ripple 支持前向引用：

```ripple
stream A <- B + 1;  // A 引用了后面定义的 B
stream B <- C + 1;  // B 引用了后面定义的 C
source C : int := 1;
```

编译器会自动解决依赖顺序。

### Q3: 如何调试复杂的循环依赖？

**A:** 使用以下策略：

1. **简化代码** - 逐步移除流，找出最小循环
2. **画图** - 在纸上画出依赖关系
3. **使用 graph 命令** - 查看完整的依赖图
4. **添加注释** - 标记每个流的用途

### Q4: 错误信息太多怎么办？

**A:** 编译器遵循**早期失败**原则：
- 先修复第一个错误
- 重新编译
- 通常后续错误会自动消失

### Q5: 如何贡献新的错误检查？

**A:** 参考 [ripple_errors.py](ripple_errors.py)：

1. 定义新的错误类
2. 在 `RippleCompilerV2` 中添加检查逻辑
3. 添加测试用例
4. 更新文档

---

## 示例：完整的错误处理流程

```python
from ripple_compiler_v2 import RippleCompilerV2

# 包含错误的代码
buggy_code = """
source A : int := 1;
stream B <- C + 1;
stream C <- D + 1;
stream D <- B + 1;  // 循环依赖
sink output <- D;
"""

compiler = RippleCompilerV2()

try:
    print("正在编译...")
    engine = compiler.run(buggy_code)
    print("编译成功！")

except Exception as e:
    print("\n编译失败！")
    print("请根据上面的错误信息修复代码。")
```

**输出：**
```
正在编译...

[词法分析] 正在分析...
✓ 生成了 34 个 tokens

[语法分析] 正在解析...
✓ 解析了 5 个语句

[编译] 开始编译...
[编译阶段 1] 检查重复定义...
[编译阶段 2] 检查未定义引用...
[编译阶段 3] 检查循环依赖...

================================================================================
Compilation failed with 3 error(s):
================================================================================

[1] Error: Circular dependency detected: B -> C -> D -> B
[2] Error: Circular dependency detected: C -> D -> B -> C
[3] Error: Circular dependency detected: D -> B -> C -> D

================================================================================

编译失败！
请根据上面的错误信息修复代码。
```

---

## 总结

Ripple 的错误处理系统提供：

✅ **编译期错误检查** - 在运行前捕获错误
✅ **详细的错误信息** - 包含位置和上下文
✅ **多种错误类型** - 循环依赖、未定义引用、重复定义等
✅ **友好的报告格式** - 易于理解和修复
✅ **扩展性** - 易于添加新的检查规则

这确保了 Ripple 程序的健壮性和可维护性！

---

## 相关资源

- [README.md](README.md) - 完整文档
- [QUICKSTART.md](QUICKSTART.md) - 快速入门
- [examples/error_examples.rpl](examples/error_examples.rpl) - 错误示例
- [ripple_errors.py](ripple_errors.py) - 错误处理 API
- [ripple_compiler_v2.py](ripple_compiler_v2.py) - 增强版编译器
