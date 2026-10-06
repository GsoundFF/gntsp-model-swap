# 角色代码与自行核对方法

本作的角色数据按**三字母代码**分目录：

```
DATA/files/chr/<code>/                散装文件
DATA/files/fpack/chr/<code>/0000.fpk  打包版
```

`--slot` 和 `--source` 用的就是这个 `<code>`。

---

## 1. 已实测确认的代码

这四个是在本作上做过替换并成功运行的，可以直接使用：

| 代码 | 角色 | 备注 |
|---|---|---|
| `krn` | 夕日红 | 三份成功记录里的目标槽位 |
| `hnt` | 雏田 | |
| `ino` | 井野 | |
| `tnd` | 纲手 | |

## 2. 全部代码（从原版游戏目录枚举）

本作 `chr/` 下有 **57 个带模型的代码**。左侧为代码，右侧为该角色 `0000.brres`
的骨骼数（实测，见 [`measured-data.md`](measured-data.md)）：

```
aaa  99    aka  66    ank 103    ari 104    asm  98    bee 172
bki  89    bnd  87    chj 169    chy 109    dei 127    dnz  99
fth  79    gai 103    gam  70    gar 122    h2b   -    hdn 148
hnt 106    hrk 153    ino 127    isu   -    ita 129    jry 139
kbt  95    kgr  96    kib  99    kir  46    kk2  97    kks  99
kkz 125    knk 104    krn  78    krs  91    ksm 122    ldy 101
lee  95    man 106    mnt 139    mth  83    nej 121    nr2 132
nrt 130    onk  99    oro 122    sai 107    sin 108    skm  98
skr 110    ssk 127    ssr 116    tel  96    ten  97    tmr 121
tnd  94    tst  93    ygo  96    ymt  93    zko  48
```

> `cmn` 不是角色，是**通用（common）**资源目录，永远不要当作槽位或来源。

**6 个代码只有散装目录、没有 FPK**：`dnz` `h2b` `isu` `onk` `tel` `tst`
（它们的 `0000.brres` 能被读出，但没有对应的 `fpack/chr/<code>/0000.fpk`）。
这类多半不是标准的可玩角色。把其中一个当作 `--source` 时，
`swap_character.py` 仍会替换散装文件，但**无法重建来源的 FPK** ——
`model` 模式下的 FPK 用的是槽位自己的原始包，所以依然能正常工作。

## 3. 部分代码看起来是罗马字缩写

例如 `nrt`≈Naruto、`ssk`≈Sasuke、`skr`≈Sakura、`kks`≈Kakashi、
`nej`≈Neji、`hnt`≈Hinata、`tmr`≈Temari、`jry`≈Jiraiya。

**可以当线索，但不要当成事实** —— 有些代码并不遵守这个规律，
靠猜会浪费一整轮构建 + 模拟器测试的时间。

## 4. 怎么可靠地确认某个代码是谁（1 分钟）

把候选代码当作来源，替换到 `krn`（夕日红）槽位上，进游戏看夕日红长什么样：

```powershell
python scripts\swap_character.py `
    --game-root <工作目录>\mod\game_root `
    --out <工作目录>\probe_<code> `
    --slot krn --source <code>
```

```powershell
Dolphin → 文件 → 打开 → <工作目录>\probe_<code>\DATA\sys\main.dol
```

进对战选**夕日红**，屏幕上出现的外观就是 `<code>` 对应的角色。
确认后删掉 `probe_<code>` 即可。

（用夕日红当"探针槽位"是因为它的骨架小、FPK 也小，构建最快。）

## 5. 想帮忙补全这张表？

欢迎提 PR：按下面格式往第 1 节加行，并写明你是怎么确认的（截图 / 步骤）。

```markdown
| `nrt` | 漩涡鸣人 | 用 krn 探针确认，2025-01-01 |
```
