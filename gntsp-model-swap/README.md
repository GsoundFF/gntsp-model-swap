# gntsp-model-swap

**火影忍者 激斗忍者大战SP（Wii）角色外观替换工具集 + AI Agent Skill**

把来源角色 **S** 的模型、贴图、调色板换到目标角色 **T** 的选人槽位上，
**T 的骨架、动作、招式、动画全部保留** —— 也就是"换皮不换招"。

> A toolset and agent skill for swapping a character's **appearance** onto
> another character's slot in *Naruto Shippuuden Gekitou Ninja Taisen! SP*
> (Wii, disc ID `3800805`), keeping the target's moves and animations intact.

本仓库不解析也不修改原始光盘镜像：产物是一棵可直接运行的目录树，
Dolphin 打开其中的 `DATA/sys/main.dol` 即可测试。

---

## 快速开始

```powershell
# 0) 一次性：把镜像解成 Dolphin 可直接运行的目录版
DolphinTool extract -i 3800805.wbfs -o <工作目录>\mod\game_root -g

# 1) 替换：雏田(hnt)的外观 -> 夕日红(krn)的槽位，招式保持夕日红的
python scripts\swap_character.py `
    --game-root <工作目录>\mod\game_root `
    --out       <工作目录>\mod\krn_as_hnt `
    --slot krn --source hnt

# 2) 校验（交付前必做）
python scripts\verify_swap.py `
    --out <工作目录>\mod\krn_as_hnt `
    --slot krn --source hnt `
    --game-root <工作目录>\mod\game_root

# 3) 测试
#    Dolphin -> 文件 -> 打开 -> <工作目录>\mod\krn_as_hnt\DATA\sys\main.dol
#    进对战模式，选「夕日红」-> 看到的是雏田的外观，招式仍是夕日红的
```

需要 Python 3.8+，**无第三方依赖**。

## 工具

| 脚本 | 用途 |
|---|---|
| [`scripts/swap_character.py`](scripts/swap_character.py) | 一键替换（散装 + FPK 两处同时改）**主入口** |
| [`scripts/verify_swap.py`](scripts/verify_swap.py) | 交付前校验：逐文件比对，证明换对了、没换错 |
| [`scripts/fpk_tool.py`](scripts/fpk_tool.py) | FPK 解包 / 重打包 / 往返自检（Eighting PRS 编解码） |
| [`scripts/brres_bones.py`](scripts/brres_bones.py) | 读骨骼表，解释"为什么不能整文件覆盖模型" |
| [`scripts/scan_characters.py`](scripts/scan_characters.py) | 扫描全部角色的模型大小与骨骼数 |

```powershell
python scripts\fpk_tool.py list     <原版.fpk>          # 查看包内条目
python scripts\fpk_tool.py roundtrip <原版.fpk>         # 编解码自检
python scripts\scan_characters.py <树干>\DATA\files\chr # 全角色骨骼数表
```

## 原理（三句话）

1. 角色数据存在**两处内容重复**的位置 —— 散装 `chr/<code>/` 与打包
   `fpack/chr/<code>/0000.fpk`，`main.dol` 两种路径都会读，所以**两处都要改**。
2. 只替换 `.brres` / `.brtex` / `.brplt`（模型 / 贴图 / 调色板），
   **保留 `0000.mot`（动画）与 `0000.seq`（招式）**。
3. 之所以必须这样：各角色骨架**数量与排列顺序都不同**（实测 46~172 根），
   而动画 `0000.mot` 按**跨角色共享的骨骼编号**寻址骨骼。
   换网格+贴图 ⇒ 编号对得上，正常显示；整文件覆盖模型 ⇒ 动画驱动错骨骼，
   模型消失或崩溃。

实测细节（骨骼表、文件大小、FPK 结构）见
[`references/measured-data.md`](references/measured-data.md)。

## 用作 AI Agent Skill

仓库根目录的 [`SKILL.md`](SKILL.md) 就是技能本体。把它放进你的 agent 技能目录即可：

```powershell
git clone https://github.com/GsoundFF/gntsp-model-swap "$env:USERPROFILE\.dsh\skills\gntsp-model-swap"
```

之后提到"把雏田的模型换到夕日红身上""火影SP换皮""这个 mod 没生效"之类，
agent 会自动加载本技能。

同样的 `SKILL.md` 格式也可以直接用于其他支持 agent skills 的环境
（Claude Skills、Codex 等），只需放到对应的 skills 目录。

## 目录结构

```
SKILL.md                        技能本体（agent 读取）
README.md
LICENSE
scripts/                        Python 工具（无依赖）
references/
  character-codes.md            角色代码表 + 自行核对方法
  file-formats.md               FPK 容器与 BRRES/MDL0 骨骼表结构
  measured-data.md              实测数据（骨骼、大小、FPK 条目）
  troubleshooting.md            排错手册
  success-records/              三次成功制作的原始流程记录
```

## 已知现象（不是 bug）

- **「无效读取」弹窗无害**：如 `从 0x00000050 读取无效，PC=0x8034c87c`，
  实测游戏正常运行，直接无视。**不要为此启用 Dolphin 的 MMU**（会变慢甚至卡住）。
- **重建后的 FPK 比原版大几个百分点**（实测 `1187936 → 1287312`，约 +8.4%）
  属正常，游戏正常载入。
- **不存在容量上限**：本方案整包重建 FPK，不像 PS2/PSP 方案那样需要原位写回。

## 免责声明

仅供个人学习、研究与单机 mod 使用。请自行拥有所修改游戏的合法副本，
不要分发游戏本体或提取出的原始资源文件。本仓库只包含工具与文档。

## 许可

MIT，见 [LICENSE](LICENSE)。
