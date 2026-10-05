# R1 Pro 商超局部操作采集（Isaac Sim）

当前阶段：源码依赖、第一个资产里程碑和 InternDataEngine 外部适配骨架已落地。**尚未完成 Isaac 物理验证、抓取专家、图像采集或 VLA 训练数据导出。**

目标是导航到站后执行 `货架→篮子`、`篮子→货架`、`篮子→冰柜`、`篮子→收货点`。不在本项目训练长程导航。

## 目录与环境

项目位于 `/home/lh/VLA/R1Pro-Market-Isaac`，依赖仓库均放在同级目录。现有 RoboBenchMart-main 和 GalaxeaVLA-main 未修改。
`dependencies.lock.json` 记录仓库、精确提交和角色；不是把所有仓库安装进同一个环境。

- Isaac Sim：以官方 R1 Pro 示例对应的 **4.5.0** 为首个验证目标。
- IsaacLab：v2.1.0，可选参考，暂未安装。
- cuRobo：v0.7.8，保留旧版 MotionGen API，暂未编译安装。
- LeRobot：使用 GalaxeaManipSim README 指定的提交，暂未安装导出依赖。
- `.venv`：独立 Python 3.10 的 **资产开发环境**，已安装 usd-core/numpy/pytest。
- Isaac 的 Python 与资产开发环境分开：**不要将本项目 usd-core wheel 装入 Isaac Python**，Isaac 自带 USD/PhysX。
- 克隆未递归下载子模块和 LFS 大文件。未下载的 LFS 指针数量已写入锁文件（目前为文档媒体/LeRobot 测试数据）；R1 Pro 官方 USD 是完整文件。
- MarketGen 是数据资产，不是已确认公开的生成器代码；完整商超数据尚未下载。
- InternDataEngine 是主数据生成编排层；GenManip、InternUtopia 和 RoboTwin 当前只作为明确边界的参考依赖。

PowerShell 用户先进入 WSL：

```powershell
wsl -d Ubuntu-22.04
```

之后使用 Linux 命令：

```bash
cd /home/lh/VLA/R1Pro-Market-Isaac
.venv/bin/python scripts/preflight.py
.venv/bin/python scripts/preflight_interndata.py
.venv/bin/python -m pytest -q
```

## 已实现

1. `configs/basket.json`：篮内尺寸、壁厚、质量、摩擦、安装坐标、有效区域。
2. `src/r1pro_market/basket.py`：五块箱形碰撞板形成真正空心容器，另含两根候选支撑柱。
3. 以引用方式组合官方机器人与篮子，通过固定关节连接真实 `base_link`；不改上游 USD。
4. 明确米/千克单位。官方源 USD 未声明 metersPerUnit，官方示例使用米；组合层按该示例设置为 1。
5. `scripts/inspect_usd.py`：检查 USD 组合和关节目标是否有效。
6. `scripts/smoke_isaac.py`：待运行的物理检查：局部任务固定底座、保持关节、测试方块落入篮子。**不是抓取演示。**
7. `scripts/generate_tasks.py`：候选任务元数据生成。示例场景只是配置示例，不是已构建的商超或训练数据。
8. 测试覆盖空腔、局部/世界安装变换、源文件不被修改、参数验证、任务可重复性和布局家族划分泄漏。
9. InternDataEngine 清单和外部插件实现 R1 Pro 双臂/双指夹爪接入骨架；未知标定值会阻止生成运行配置。

安装位置是候选值 `[0.45, 0, 0.65]` 米（相对于官方底座连杆），尚未确认双臂可达、动态碰撞、真实机械结构承载。两根柱仅用于初步仿真外形，不是获厂商认可的安装方案。

## 资产生成和检查

首次构建：

```bash
.venv/bin/python scripts/build_assets.py
.venv/bin/python scripts/inspect_usd.py assets/generated/r1pro_with_basket.usda --report reports/assembly_audit.json
```

已有资产不会被静默覆盖。调整参数后输出到新目录：

```bash
.venv/bin/python scripts/build_assets.py --output-dir assets/generated/revision_02
```

生成的 `r1pro_with_basket.usda` 引用同级官方仓库。移动该资产时需要保持引用路径或重新生成；它不是一个包含所有网格的独立打包文件。
导出的机器人没有固定到世界。物理 smoke 脚本只在自己的测试 Stage 中固定底座，符合局部操作边界。

## 下一关：Isaac 物理检查

自动检查未在常见 Linux/Windows 位置找到 Isaac Sim。请先提供已有安装的 `python.sh` 路径，或安装 Isaac Sim 4.5.0。
这不是 CPU 单元测试能替代的步骤；8GB 显存先只运行一个局部场景实例。

```bash
export ISAAC_PYTHON=/实际的/isaacsim/python.sh
bash scripts/run_isaac.sh --gui
```

报告输出：`reports/isaac_smoke.json`。只有真实执行通过才会写入 `physics_simulated: true`。
检查方块留在篮内、速度收敛、篮子无异常漂移；这个通过后仍需双臂可达性和抓放测试。
运行脚本参数必须与用于构建资产的篮子参数一致；自定义资产时同时传入 --asset 和 --basket-config（默认使用 configs/basket.json）。

## 候选任务配置

```bash
.venv/bin/python scripts/generate_tasks.py --count 20 --seed 42
```

输出 `datasets/candidates/example.jsonl` 中每条记录都标记 `candidate_unvalidated`。
当前生成器只支持直立盒状尺寸约束；尚未做碰撞、IK、遮挡、专家执行或物理成功验证。
同一布局家族必须归属于同一 split。真实场景接入时须将示例 snapshot 替换为可恢复的场景状态。
文件存在时拒绝覆盖，改 output 路径或 seed 生成另一批。

## 后续顺序

- M0 已完成：依赖克隆、版本记录、开发环境。
- M1 已完成结构部分：篮子生成、机器人组合、CPU/USD 测试。
- M1 待完成运行部分：Isaac 启动、持姿/落物、双臂可达、抓放验证。
- M1.5 已完成静态部分：InternDataEngine 插件、URDF/USD 合同检查、按名称解析 DOF；运行标定仍待 Isaac 4.5。
- M2：接入一个 MarketGen 局部货架，建立商品/支撑面/入口/目标区域标注。
- M3：同步规划碰撞世界，实现货架→篮子的专家；考虑持物体积和夹爪接触。
- M4：记录 `obs_t → action_t → obs_(t+1)`，同步真实头部/左右腕图像；恢复初始状态回放。
- M5：导出 LeRobot、验证训练读取，扩展另外三类任务。
- M6：固定场景家族划分、按任务覆盖配额批量生成与闭环评估。

不要将候选 JSON、USD 结构测试或关节瞬移示例当作成功操作轨迹。

## 上游资源

- https://cnb.cool/open_source/galaxea_isaac_tutorial
- https://github.com/OpenGalaxea/GalaxeaManipSim
- https://github.com/RoboTwin-Platform/RoboTwin
- https://github.com/NVlabs/curobo
- https://github.com/isaac-sim/IsaacLab
- https://github.com/huggingface/lerobot
- https://github.com/OpenGalaxea/GalaxeaVLA
- https://github.com/InternRobotics/InternDataEngine
- https://github.com/InternRobotics/GenManip
- https://github.com/InternRobotics/InternUtopia
- https://huggingface.co/datasets/HXX/MarketGen

上游代码和模型保留原有许可。当前项目通过引用使用资产，没有给上游资产重新授予许可。
