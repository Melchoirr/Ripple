# Ripple 语言 - 更新日志

## [1.0.1] - 2025-12-09

### 🐛 Bug 修复

**修复 Lambda 表达式作用域问题**
- 问题：`extract_dependencies` 函数错误地将 Lambda 参数（如 `acc`, `x`）识别为外部依赖
- 影响：使用 `fold` 操作符的代码会报"未定义引用"错误
- 修复：增强 `extract_dependencies` 函数，正确处理 Lambda 表达式的局部作用域
- 文件：`ripple_ast.py`

**修复前：**
```ripple
stream sum <- fold(numbers, 0, (acc, x) => acc + x);
// 错误：Undefined reference 'acc' in 'sum'
// 错误：Undefined reference 'x' in 'sum'
```

**修复后：**
```ripple
stream sum <- fold(numbers, 0, (acc, x) => acc + x);
// ✓ 编译成功！
```

### ✅ 测试改进

- 测试通过率：93.3% → **100%** 🎉
- 所有 15 个测试现在全部通过
- 新增 FAQ 说明 Lambda 作用域处理

### 📚 文档更新

- 更新 README.md - 反映 100% 测试通过率
- 更新 ERROR_HANDLING.md - 添加 Lambda 作用域 FAQ
- 更新 PROJECT_STATUS.txt - 更新测试统计

---

## [1.0.0] - 2025-12-09

### 🎉 初始发布

**核心特性**
- ✅ 完整的编译器实现（词法、语法、语义分析）
- ✅ 强大的错误检测系统（循环依赖、未定义引用、重复定义）
- ✅ 零故障传播保证（基于拓扑排序）
- ✅ 响应式图引擎（Push-Pull 模型）

**语言特性**
- ✅ 源声明（Source）
- ✅ 流声明（Stream）
- ✅ 输出节点（Sink）
- ✅ Pre 操作符（访问历史值）
- ✅ Fold 操作符（状态累积）
- ✅ 条件表达式（if-then-else）
- ✅ Lambda 表达式

**工具**
- ✅ 交互式运行器
- ✅ 测试套件（15个测试）
- ✅ 完整文档（README, QUICKSTART, ERROR_HANDLING）
- ✅ 6个示例程序

**文件清单**
- 7个核心实现文件（~2300行）
- 2个工具文件
- 6个示例文件
- 4个文档文件

---

## 技术细节

### Lambda 作用域修复详情

**问题分析：**

原始的 `extract_dependencies` 函数在处理 `FoldOp` 时：
```python
elif isinstance(node, FoldOp):
    visit(node.stream)
    visit(node.initial)
    visit(node.accumulator.body)  # 直接访问 body，没有考虑参数
```

这导致 Lambda 的参数 `acc` 和 `x` 被错误地识别为外部依赖。

**修复方案：**

新的实现引入了 `local_vars` 参数来追踪局部变量：
```python
def extract_dependencies(expr: Expression, local_vars: set = None) -> List[str]:
    # ...
    def visit(node, locals_set):
        if isinstance(node, Identifier):
            # 只有不在局部变量集合中的标识符才是外部依赖
            if node.name not in locals_set:
                dependencies.append(node.name)
        # ...
        elif isinstance(node, FoldOp):
            visit(node.stream, locals_set)
            visit(node.initial, locals_set)

            # Lambda body 使用扩展的作用域（包含 Lambda 参数）
            if isinstance(node.accumulator, Lambda):
                lambda_locals = locals_set.copy()
                lambda_locals.update(node.accumulator.parameters)
                visit(node.accumulator.body, lambda_locals)
```

**关键改进：**
1. 添加 `local_vars` 参数追踪局部变量作用域
2. 在访问 Lambda body 前，将 Lambda 参数加入局部变量集合
3. `Identifier` 检查时，过滤掉局部变量

**测试验证：**
- 测试 15（Fold 操作）现在通过 ✓
- 所有其他测试不受影响
- 总通过率：100%

---

## 下一步计划

- [ ] 完善 Pre 操作符的实现
- [ ] 添加更多内置函数
- [ ] 实现类型推导系统
- [ ] 添加高阶流（Stream of Streams）
- [ ] 性能优化（Slab 内存分配）

---

**维护者**: Ripple 开发团队
**许可证**: 实验性研究项目
