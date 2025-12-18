"""
Ripple 语言综合测试
测试所有主要特性：结构体、pre、fold、函数、let、数组
"""

from ripple_compiler import RippleCompiler


def test_basic_struct():
    """测试基础结构体功能"""
    print("=" * 60)
    print("测试 1: 基础结构体 - 类型定义、字段访问、字段级更新")
    print("=" * 60)

    code = """
    type Point = { x: int, y: int };

    source p : Point := { x: 3, y: 4 };

    stream px <- p.x;
    stream py <- p.y;

    func square(n) = n * n;
    stream distance <- sqrt(square(p.x) + square(p.y));

    sink px_out <- px;
    sink py_out <- py;
    sink dist_out <- distance;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("\n初始状态:")
    outputs = engine.get_sink_outputs()
    print(f"  px = {outputs['px_out']} (预期: 3)")
    print(f"  py = {outputs['py_out']} (预期: 4)")
    print(f"  distance = {outputs['dist_out']} (预期: 5.0)")

    assert outputs['px_out'] == 3
    assert outputs['py_out'] == 4
    assert outputs['dist_out'] == 5.0

    # 测试字段级更新
    print("\n字段级更新: p.x = 6")
    engine.push_event('p.x', 6)
    outputs = engine.get_sink_outputs()
    print(f"  px = {outputs['px_out']} (预期: 6)")
    print(f"  py = {outputs['py_out']} (预期: 4, 不变)")
    print(f"  distance = {outputs['dist_out']:.2f} (预期: 7.21)")

    assert outputs['px_out'] == 6
    assert outputs['py_out'] == 4  # 不变
    assert abs(outputs['dist_out'] - 7.211) < 0.01

    # 测试整体更新
    print("\n整体更新: p = {x: 0, y: 0}")
    engine.push_event('p', {'x': 0, 'y': 0})
    outputs = engine.get_sink_outputs()
    print(f"  px = {outputs['px_out']} (预期: 0)")
    print(f"  py = {outputs['py_out']} (预期: 0)")
    print(f"  distance = {outputs['dist_out']} (预期: 0.0)")

    assert outputs['px_out'] == 0
    assert outputs['py_out'] == 0
    assert outputs['dist_out'] == 0.0

    print("\n✓ 测试通过!")


def test_struct_with_pre():
    """测试结构体与 pre 操作符结合"""
    print("\n" + "=" * 60)
    print("测试 2: 结构体 + Pre 操作符 - 计数器与状态追踪")
    print("=" * 60)

    code = """
    type Counter = { value: int, step: int };

    // 计数器源
    source counter : Counter := { value: 0, step: 1 };

    // 累计值：每次 value 更新时，累加 step
    stream total <- pre(total, 0) + counter.step on counter.value;

    // 更新次数
    stream update_count <- pre(update_count, 0) + 1 on counter.value;

    // 最大值追踪
    func max_val(a, b) = if a > b then a else b end;
    stream max_value <- max_val(pre(max_value, 0), counter.value) on counter.value;

    sink value_out <- counter.value;
    sink step_out <- counter.step;
    sink total_out <- total;
    sink count_out <- update_count;
    sink max_out <- max_value;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    # 注意：初始化时所有节点都会计算一次，所以 total 和 update_count 初始值为 1
    print("\n初始状态 (counter = {value: 0, step: 1}):")
    outputs = engine.get_sink_outputs()
    print(f"  value = {outputs['value_out']} (预期: 0)")
    print(f"  step = {outputs['step_out']} (预期: 1)")
    print(f"  total = {outputs['total_out']} (预期: 1, 初始计算)")
    print(f"  update_count = {outputs['count_out']} (预期: 1, 初始计算)")
    print(f"  max_value = {outputs['max_out']} (预期: 0)")

    assert outputs['value_out'] == 0
    assert outputs['step_out'] == 1
    assert outputs['total_out'] == 1  # 初始计算: pre(0) + step(1) = 1
    assert outputs['count_out'] == 1  # 初始计算: pre(0) + 1 = 1
    assert outputs['max_out'] == 0

    # 更新 value 为 5
    print("\n更新 counter.value = 5:")
    engine.push_event('counter.value', 5)
    outputs = engine.get_sink_outputs()
    print(f"  value = {outputs['value_out']} (预期: 5)")
    print(f"  total = {outputs['total_out']} (预期: 2, 1+step=1)")
    print(f"  update_count = {outputs['count_out']} (预期: 2)")
    print(f"  max_value = {outputs['max_out']} (预期: 5)")

    assert outputs['value_out'] == 5
    assert outputs['total_out'] == 2  # pre(1) + step(1) = 2
    assert outputs['count_out'] == 2  # pre(1) + 1 = 2
    assert outputs['max_out'] == 5

    # 更新 step 为 10（不触发 total 和 count，因为 on counter.value）
    print("\n更新 counter.step = 10:")
    engine.push_event('counter.step', 10)
    outputs = engine.get_sink_outputs()
    print(f"  step = {outputs['step_out']} (预期: 10)")
    print(f"  total = {outputs['total_out']} (预期: 2, 不变)")
    print(f"  update_count = {outputs['count_out']} (预期: 2, 不变)")

    assert outputs['step_out'] == 10
    assert outputs['total_out'] == 2  # step 更新不触发 total
    assert outputs['count_out'] == 2

    # 再次更新 value
    print("\n更新 counter.value = 3:")
    engine.push_event('counter.value', 3)
    outputs = engine.get_sink_outputs()
    print(f"  value = {outputs['value_out']} (预期: 3)")
    print(f"  total = {outputs['total_out']} (预期: 12, 2+step=10)")
    print(f"  update_count = {outputs['count_out']} (预期: 3)")
    print(f"  max_value = {outputs['max_out']} (预期: 5, 保持最大值)")

    assert outputs['value_out'] == 3
    assert outputs['total_out'] == 12  # pre(2) + step(10) = 12
    assert outputs['count_out'] == 3   # pre(2) + 1 = 3
    assert outputs['max_out'] == 5     # max(5, 3) = 5

    # 更新 value 为 10
    print("\n更新 counter.value = 10:")
    engine.push_event('counter.value', 10)
    outputs = engine.get_sink_outputs()
    print(f"  value = {outputs['value_out']} (预期: 10)")
    print(f"  max_value = {outputs['max_out']} (预期: 10, 新最大值)")

    assert outputs['value_out'] == 10
    assert outputs['max_out'] == 10

    print("\n✓ 测试通过!")


def test_struct_with_fold():
    """测试结构体与 fold 操作符结合"""
    print("\n" + "=" * 60)
    print("测试 3: 结构体 + Fold 操作符 - 统计数据聚合")
    print("=" * 60)

    code = """
    type Stats = { count: int, sum: int };

    // 数据源
    source data : [int] := [1, 2, 3, 4, 5];

    // 使用 fold 计算统计信息
    stream stats <- fold(data, { count: 0, sum: 0 }, (acc, x) => {
        count: acc.count + 1,
        sum: acc.sum + x
    });

    // 提取字段
    stream count <- stats.count;
    stream total <- stats.sum;
    stream average <- stats.sum / stats.count;

    sink count_out <- count;
    sink total_out <- total;
    sink avg_out <- average;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("\n数据: [1, 2, 3, 4, 5]")
    outputs = engine.get_sink_outputs()
    print(f"  count = {outputs['count_out']} (预期: 5)")
    print(f"  sum = {outputs['total_out']} (预期: 15)")
    print(f"  average = {outputs['avg_out']} (预期: 3.0)")

    assert outputs['count_out'] == 5
    assert outputs['total_out'] == 15
    assert outputs['avg_out'] == 3.0

    # 更新数据
    print("\n更新数据为: [10, 20, 30]")
    engine.push_event('data', [10, 20, 30])
    outputs = engine.get_sink_outputs()
    print(f"  count = {outputs['count_out']} (预期: 3)")
    print(f"  sum = {outputs['total_out']} (预期: 60)")
    print(f"  average = {outputs['avg_out']} (预期: 20.0)")

    assert outputs['count_out'] == 3
    assert outputs['total_out'] == 60
    assert outputs['avg_out'] == 20.0

    print("\n✓ 测试通过!")


def test_struct_array_operations():
    """测试结构体与数组操作结合"""
    print("\n" + "=" * 60)
    print("测试 4: 结构体数组 - map/filter/reduce")
    print("=" * 60)

    code = """
    // 点数组
    source points : [{ x: int, y: int }] := [
        { x: 1, y: 2 },
        { x: 3, y: 4 },
        { x: 5, y: 6 }
    ];

    // 提取所有 x 坐标
    stream x_coords <- map(points, (p) => p.x);

    // 过滤 x > 2 的点
    stream filtered <- filter(points, (p) => p.x > 2);

    // 计算所有 x 坐标的和
    stream x_sum <- reduce(x_coords, 0, (acc, x) => acc + x);

    // 计算 y 坐标的和
    stream y_sum <- reduce(points, 0, (acc, p) => acc + p.y);

    sink x_coords_out <- x_coords;
    sink filtered_out <- filtered;
    sink x_sum_out <- x_sum;
    sink y_sum_out <- y_sum;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("\n点数组: [{x:1,y:2}, {x:3,y:4}, {x:5,y:6}]")
    outputs = engine.get_sink_outputs()
    print(f"  x坐标列表 = {outputs['x_coords_out']} (预期: [1, 3, 5])")
    print(f"  过滤(x>2) = {outputs['filtered_out']} (预期: 2个点)")
    print(f"  x坐标和 = {outputs['x_sum_out']} (预期: 9)")
    print(f"  y坐标和 = {outputs['y_sum_out']} (预期: 12)")

    assert outputs['x_coords_out'] == [1, 3, 5]
    assert len(outputs['filtered_out']) == 2
    assert outputs['x_sum_out'] == 9
    assert outputs['y_sum_out'] == 12

    print("\n✓ 测试通过!")


def test_complex_scenario():
    """复杂场景：游戏角色状态管理"""
    print("\n" + "=" * 60)
    print("测试 5: 复杂场景 - 游戏角色状态管理")
    print("=" * 60)

    code = """
    // 类型定义
    type Position = { x: int, y: int };
    type Character = { hp: int, maxHp: int };

    // 角色状态
    source player : Character := { hp: 100, maxHp: 100 };
    source pos : Position := { x: 0, y: 0 };

    // 伤害事件
    source damage : int := 0;

    // 计算当前血量
    func clamp(val, minVal, maxVal) =
        if val < minVal then minVal
        else if val > maxVal then maxVal
        else val end end;

    stream current_hp <- clamp(player.hp - damage, 0, player.maxHp);

    // 是否存活
    stream is_alive <- current_hp > 0;

    // 血量百分比
    stream hp_percent <- current_hp * 100 / player.maxHp;

    // 移动历史（使用 pre 记录）
    stream prev_pos <- { x: pre(prev_pos_x, 0), y: pre(prev_pos_y, 0) };
    stream prev_pos_x <- pos.x on pos.x;
    stream prev_pos_y <- pos.y on pos.y;

    // 总移动步数
    stream steps <- pre(steps, 0) + 1 on pos.x;

    sink hp_out <- current_hp;
    sink alive_out <- is_alive;
    sink percent_out <- hp_percent;
    sink pos_x_out <- pos.x;
    sink pos_y_out <- pos.y;
    sink steps_out <- steps;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    # 注意：初始化时 steps 会计算一次，所以初始值为 1
    print("\n初始状态:")
    outputs = engine.get_sink_outputs()
    print(f"  血量: {outputs['hp_out']}/{100} ({outputs['percent_out']}%)")
    print(f"  存活: {outputs['alive_out']}")
    print(f"  位置: ({outputs['pos_x_out']}, {outputs['pos_y_out']})")
    print(f"  步数: {outputs['steps_out']} (预期: 1, 初始计算)")

    assert outputs['hp_out'] == 100
    assert outputs['alive_out'] == True
    assert outputs['steps_out'] == 1  # 初始计算: pre(0) + 1 = 1

    # 受到伤害
    print("\n受到 30 点伤害:")
    engine.push_event('damage', 30)
    outputs = engine.get_sink_outputs()
    print(f"  血量: {outputs['hp_out']}/{100} ({outputs['percent_out']}%)")
    print(f"  存活: {outputs['alive_out']}")

    assert outputs['hp_out'] == 70
    assert outputs['percent_out'] == 70
    assert outputs['alive_out'] == True

    # 移动
    print("\n移动到 (5, 0):")
    engine.push_event('pos.x', 5)
    outputs = engine.get_sink_outputs()
    print(f"  位置: ({outputs['pos_x_out']}, {outputs['pos_y_out']})")
    print(f"  步数: {outputs['steps_out']} (预期: 2)")

    assert outputs['pos_x_out'] == 5
    assert outputs['steps_out'] == 2  # pre(1) + 1 = 2

    # 致命伤害
    print("\n受到 100 点伤害:")
    engine.push_event('damage', 100)
    outputs = engine.get_sink_outputs()
    print(f"  血量: {outputs['hp_out']}/{100}")
    print(f"  存活: {outputs['alive_out']}")

    assert outputs['hp_out'] == 0
    assert outputs['alive_out'] == False

    print("\n✓ 测试通过!")


def test_nested_struct():
    """测试嵌套结构体"""
    print("\n" + "=" * 60)
    print("测试 6: 嵌套结构体字面量")
    print("=" * 60)

    code = """
    source x : int := 1;
    source y : int := 2;

    // 动态构建嵌套结构体 (注意: 'end' 是关键字，使用 'finish' 代替)
    stream line <- {
        start: { x: 0, y: 0 },
        finish: { x: x * 10, y: y * 10 }
    };

    // 访问嵌套字段
    stream finish_x <- line.finish.x;
    stream finish_y <- line.finish.y;

    sink line_out <- line;
    sink finish_x_out <- finish_x;
    sink finish_y_out <- finish_y;
    """

    compiler = RippleCompiler()
    engine = compiler.run(code)

    print("\nx=1, y=2 时:")
    outputs = engine.get_sink_outputs()
    print(f"  line = {outputs['line_out']}")
    print(f"  finish.x = {outputs['finish_x_out']} (预期: 10)")
    print(f"  finish.y = {outputs['finish_y_out']} (预期: 20)")

    assert outputs['finish_x_out'] == 10
    assert outputs['finish_y_out'] == 20

    print("\n更新 x=5:")
    engine.push_event('x', 5)
    outputs = engine.get_sink_outputs()
    print(f"  line = {outputs['line_out']}")
    print(f"  finish.x = {outputs['finish_x_out']} (预期: 50)")

    assert outputs['finish_x_out'] == 50

    print("\n✓ 测试通过!")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Ripple 语言综合测试")
    print("=" * 60)

    try:
        test_basic_struct()
        test_struct_with_pre()
        test_struct_with_fold()
        test_struct_array_operations()
        test_complex_scenario()
        test_nested_struct()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
