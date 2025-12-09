# Ripple 语言快速入门

## 5 分钟了解 Ripple

Ripple 是一种**原生响应式流语言**，它让数据自动流动。

### 传统编程 vs Ripple

**传统方式（Python）：**
```python
# 需要手动管理更新
a = 1
b = a * 2  # b = 2
c = a + 1  # c = 2
d = b + c  # d = 4

# 当 a 改变时...
a = 5
# b、c、d 不会自动更新！
# 必须手动重新计算
b = a * 2  # b = 10
c = a + 1  # c = 6
d = b + c  # d = 16
```

**Ripple 方式：**
```ripple
source A : int := 1;
stream B <- A * 2;
stream C <- A + 1;
stream D <- B + C;

// 当 A 变为 5 时，B、C、D 自动更新！
// 就像 Excel 中的单元格公式
```

## 安装和运行

### 步骤 1: 准备环境

```bash
# 确保有 Python 3.8+
python --version

# 进入项目目录
cd adsl
```

### 步骤 2: 运行演示

```bash
# 运行完整演示
python demo.py

# 或运行交互式示例
python ripple_runner.py examples/example1_diamond.rpl
```

### 步骤 3: 编写你的第一个程序

创建文件 `my_first.rpl`:

```ripple
// 温度转换器
source celsius : float := 0.0;
stream fahrenheit <- celsius * 9.0 / 5.0 + 32.0;
stream is_freezing <- celsius <= 0.0;
stream is_hot <- celsius >= 30.0;

sink temp_f <- fahrenheit;
sink freezing <- is_freezing;
sink hot <- is_hot;
```

运行：

```bash
python ripple_runner.py my_first.rpl
```

在交互模式中输入：

```
> celsius = 25
推送事件: celsius = 25.0

当前输出：
--------------------------------------------------------------------------------
  temp_f = 77.0
  freezing = False
  hot = False
--------------------------------------------------------------------------------

> celsius = -10
推送事件: celsius = -10.0

当前输出：
--------------------------------------------------------------------------------
  temp_f = 14.0
  freezing = True
  hot = False
--------------------------------------------------------------------------------
```

## 核心概念

### 1. Source（源）

外部输入，由你控制：

```ripple
source price : float := 100.0;
source enabled : bool := true;
```

### 2. Stream（流）

自动计算的值，当依赖改变时自动更新：

```ripple
stream doubled <- price * 2;
stream status <- if enabled then "ON" else "OFF" end;
```

### 3. Sink（输出）

你想观察的结果：

```ripple
sink output <- doubled;
sink message <- status;
```

### 4. 特殊操作符

#### Pre - 访问历史值

```ripple
source tick : int := 0;
stream counter <- pre(counter, 0) + 1;
// counter 从 0 开始，每次递增
```

#### Fold - 累积计算

```ripple
source numbers : int := 0;
stream sum <- fold(numbers, 0, (acc, x) => acc + x);
// 累加所有输入的数字
```

## 实际应用示例

### 示例 1: 购物车

```ripple
source item_price : float := 0.0;
source tax_rate : float := 0.08;

stream total <- fold(item_price, 0.0, (acc, price) => acc + price);
stream tax <- total * tax_rate;
stream grand_total <- total + tax;

sink cart_total <- total;
sink cart_tax <- tax;
sink final_price <- grand_total;
```

使用：
```
> item_price = 10.0   // 添加 $10 商品
> item_price = 25.0   // 添加 $25 商品
> item_price = 15.0   // 添加 $15 商品
// total = 50.0, tax = 4.0, grand_total = 54.0
```

### 示例 2: 温度监控

```ripple
source temp : float := 20.0;

stream temp_status <- if temp < 15.0 then "冷"
                      else if temp < 25.0 then "舒适"
                      else "热" end end;

stream alert <- if temp < 10.0 || temp > 30.0 then "警告！"
                else "正常" end;

sink status <- temp_status;
sink alarm <- alert;
```

### 示例 3: 数据统计

```ripple
source value : float := 0.0;

stream sum <- fold(value, 0.0, (acc, x) => acc + x);
stream count <- fold(value, 0.0, (acc, x) => acc + 1.0);
stream average <- sum / count;
stream max <- fold(value, 0.0, (acc, x) => if x > acc then x else acc end);

sink avg_out <- average;
sink max_out <- max;
```

## 交互式运行器命令

运行 `python ripple_runner.py <file.rpl>` 后，可用命令：

| 命令 | 说明 | 示例 |
|------|------|------|
| `source_name = value` | 推送值到源 | `A = 5` |
| `graph` | 显示依赖图 | `graph` |
| `outputs` | 显示当前输出 | `outputs` |
| `sources` | 列出所有源 | `sources` |
| `help` | 显示帮助 | `help` |
| `quit` / `exit` / `q` | 退出 | `quit` |

## 常见问题

### Q: Ripple 和 RxJS 有什么区别？

**A:** RxJS 是一个库，需要显式调用 `subscribe()`。Ripple 是一门语言，依赖关系由编译器自动管理。

### Q: 什么时候用 Pre，什么时候用 Fold？

**A:**
- **Pre**: 需要访问**前一个时刻**的值时（如计数器）
- **Fold**: 需要**累积所有历史**数据时（如求和）

### Q: 支持哪些数据类型？

**A:** 当前支持：
- `int` - 整数
- `float` - 浮点数
- `bool` - 布尔值
- `string` - 字符串

### Q: 如何调试？

**A:**
1. 使用 `graph` 命令查看依赖关系
2. 使用 `outputs` 命令查看当前所有输出
3. 逐步推送事件，观察值的变化

## 下一步

- 查看 [examples/](examples/) 目录中的更多示例
- 阅读完整的 [README.md](README.md) 了解架构
- 阅读设计文档了解理论基础

## 获取帮助

遇到问题？

1. 检查语法是否正确
2. 确保所有依赖的 source 都已定义
3. 查看示例代码作为参考
4. 运行 `python <module>.py` 测试各个模块

**祝你使用 Ripple 愉快！** 🌊
