# InternDataEngine 接入边界

当前接入选择是 Isaac Sim 4.5 + InternDataEngine + cuRobo。GenManip 用于参考任务和语言生成，
InternUtopia 用于参考 GRScenes 和场景加载，RoboTwin 只参考专家任务结构。它们不被混装成一个
Python 环境，也不把 SAPIEN 控制器直接迁入 Isaac。

## 已落地

- dependencies.lock.json 固定 InternDataEngine、GenManip、InternUtopia 的实际提交。
- configs/interndata/r1pro_manifest.json 记录官方 URDF/USD 中可核验的关节、末端、相机和夹爪范围。
- src/r1pro_market/interndata_plugin.py 注册外部机器人和控制器，不修改上游仓库。
- 插件处理组合 USD 的嵌套 articulation root，移动机器人时让篮子随整个组合层移动，并把每侧两个夹爪关节映射为开关动作。
- scripts/preflight_interndata.py 检查依赖提交、URDF、USD 路径、Isaac 报告和未完成标定。
- scripts/generate_interndata_robot_config.py 只在物理 smoke 和标定均完成后生成引擎配置。

## 为什么现在仍显示 blocked

这是有意的安全门。CPU 环境可以核验静态结构，但以下数据必须来自 Isaac 4.5 实测：

1. articulation 初始化后的完整 dof_names 顺序；
2. 左右臂 cuRobo 配置和碰撞球；
3. TCP 相对左右 gripper_link 的偏移；
4. GraspNet 到 R1 Pro 末端坐标的旋转矩阵和进近轴；
5. 允许接触夹爪、禁止碰撞手臂的 prim 列表；
6. 篮子安装候选在持姿、落物、双臂可达和自碰撞检查中通过。

这些值未验证前，脚本拒绝生成可运行的机器人 YAML，防止能启动但轨迹错误的静默失败。

## 执行顺序

CPU 或资产环境：

    .venv/bin/python scripts/preflight_interndata.py
    .venv/bin/python -m pytest -q

Isaac 4.5 环境：

    export ISAAC_PYTHON=/path/to/isaac-sim/python.sh
    bash scripts/run_isaac.sh --gui
    .venv/bin/python scripts/preflight_interndata.py --require-runtime

物理报告通过、清单标定完成后：

    .venv/bin/python scripts/generate_interndata_robot_config.py

之后才能为一个局部货架场景写 InternDataEngine task YAML，并通过：

    "$ISAAC_PYTHON" scripts/run_interndata.py --engine-root ../InternDataEngine \
      --config /absolute/path/to/engine_workflow.yaml

task YAML 需要指定绝对 asset_root 或把场景资产放到统一资产根目录。MarketGen 或 GRScenes
不能只靠 USD 文件名自动变成操作任务；商品可动刚体、货架碰撞、可放置区域、抓取对象和成功条件仍要标注。
