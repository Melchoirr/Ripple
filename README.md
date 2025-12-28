# Ripple 语言

Ripple 是一种声明式、响应式的数据流 DSL，支持增量计算和 CSV 热更新。

## 核心概念

| 关键字 | 说明 |
|--------|------|
| `source` | 输入源，可交互修改 |
| `stream` | 计算流，依赖变化时自动更新 |
| `sink` | 输出端，显示最终结果 |

## 语法示例

```ripple
source x : int := 10;
stream y <- x * 2;
sink out <- y;
```

## 语言特性

- **基本类型**：`int`, `float`, `bool`, `string`
- **复合类型**：`array<T>`, `struct { field: type }`
- **运算符**：`+`, `-`, `*`, `/`, `%`, `&&`, `||`, `>`, `<`, `==`
- **条件表达式**：`if cond then a else b`
- **高阶函数**：`map`, `filter`, `reduce`
- **聚合函数**：`sum`, `avg`, `max`, `min`, `len`
- **时态操作**：`pre`（前值）, `fold`（累积）, `on`（触发）
- **CSV 加载**：`load_csv("file.csv", true)` 支持热更新

## 运行方式

```bash
# 运行示例
python ripple_runner.py examples/01_basic.rpl

# 交互命令
> x = 20        # 修改 source 值
> :show         # 显示所有节点状态
> :quit         # 退出
```

## 示例文件

| 文件 | 内容 |
|------|------|
| `01_basic.rpl` | 基础语法、算术运算 |
| `02_diamond.rpl` | 菱形依赖、glitch-free 传播 |
| `03_conditional.rpl` | 条件表达式 |
| `04_function.rpl` | 函数定义、递归 |
| `05_array.rpl` | 数组操作 |
| `06_aggregate.rpl` | 聚合函数 |
| `07_matrix.rpl` | 矩阵运算 |
| `08_struct.rpl` | 结构体 |
| `09_temporal.rpl` | 时态操作 |
| `10_csv.rpl` | CSV 加载与热更新 |
| `11_type_inference.rpl` | 类型推导演示 |
| `12_student_system.rpl` | 综合示例 |

## 依赖

```bash
pip install watchdog  # CSV 热更新（可选）
```
