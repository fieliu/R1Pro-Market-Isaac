# 实施记录与接口边界

本项目是新的 Isaac 后端，不将原 ManiSkill 与 GalaxeaManipSim 运行时混装。

## 当前验证状态

CPU/USD 测试通过不代表机器人能抓取。generated 下资产是可检查的初版，需 Isaac 验证后才能用于采集。
详见 reports/assembly_audit.json、reports/isaac_smoke.json 和 reports/preflight.json。

## 发现的上游差异

- R1Pro 官方 Isaac USD：两臂各 7 个转动关节，左右夹爪各 2 个移动关节；底座、躯干、双臂都有物理刚体。
- 原 USD 缺少显式米制声明，官方示例 World(stage_units_in_meters=1.0)；这里明确写入米制组合层。
- 官方 whole_body_move.py 使用 set_joint_positions，是演示用状态设置；数据采集必须改为 drive/action 控制。
- 本地 ds_r1 配置操作左臂 6 关节，不能直接视为完整 R1 Pro 双臂。
- 本地 Fetch 导出脚本固定 15/13 维并复制腕部图像，不能原样复用于本项目。
- cuRobo 最新主线已经是不同 API，锁定 v0.7.8。
- LeRobot 克隆后锁定 GalaxeaManipSim 文档中的提交，避免当前主线 Python/API 差异。
- 动态篮子的碰撞为多个箱体，不将篮子整体做成封闭凸包。
- 专家可用仿真真值，训练观测应严格限制为部署可获得的输入。
- 固定关节只禁用直接相连的底座与篮子之间碰撞，不全局禁用手臂与篮子碰撞。

## 后续任务接口（设计，尚未实现）

SimulatorAdapter: reset(snapshot), observe(), step(action), state(), object_pose(id)
PlannerAdapter: update_world(), candidate_grasps(), plan(), attach_collision_geometry(), detach()
Expert: structured TaskSpec -> staged actions with timeout/retry and failure reason
Recorder: observe BEFORE action, then execute, retain terminal observation separately
Success: correct object + correct region + released + stable + arm retracted
Exporter: actual camera identifiers, joint ordering, units, control period, task text

先验证右手取放，再验证左手可达；两只手同时运动需要独立验证互碰，不能视为自然支持。
无门冰柜/已开门冰柜与带开关门任务分阶段实现。

## 未完成项

Isaac 运行时安装或路径确认；篮子真实可达/动态稳定性；相机标定；MarketGen 下载与物理预处理；
cuRobo 编译及 R1 Pro 配置；四类专家；同步记录与 LeRobot 导出；真实训练与策略评估。
