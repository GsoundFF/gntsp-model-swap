# 排错手册

## 0. 三步快速诊断

```powershell
# 1) 这个 mod 到底换对了没有？（不用开游戏）
python scripts\verify_swap.py --out <mod树> --slot <T> --source <S> --game-root <原始树>
```

```powershell
# 2) FPK 格式本身合法吗？
python scripts\fpk_tool.py roundtrip <mod树>\DATA\files\fpack\chr\<T>\0000.fpk
```

```powershell
# 3) 骨架差异有多大？（解释"为什么不能整文件换模型"）
python scripts\brres_bones.py <原始树>\...\chr\<T>\0000.brres <原始树>\...\chr\<S>\0000.brres
```

`verify_swap.py` 退出码 0 且全绿 ⇒ **文件层面已经完成**，剩下的问题一定在
模拟器侧或认知侧（看错角色、没冷启动、看的不是新目录）。

---

## 1. 「完全没变化」

按可能性从高到低：

1. **Dolphin 打开的不是新目录。**
   确认打开的是 `<mod树>\DATA\sys\main.dol`，不是一个旧的 mod 目录，
   也不是 `.wbfs` 镜像（镜像里永远是原版）。
2. **没有冷启动。**
   如果你读的是战斗中的即时存档，模型不会重新加载。
   请完全关闭游戏进程重新进入。
3. **选错了角色。**
   外观出现在**目标角色 T**的槽位上。做的是"雏田换夕日红"，
   就要**选夕日红**去看雏田 —— 选雏田只会看到原版雏田。
   方向搞反是这个工作里最常见的错误。
4. **`--game-root` 用错了。**
   必须是**原始**树。拿已经改过的树再换一次，结果不可预测。

## 2. 「只有部分画面变了」

本作同时存在两条读取路径，`main.dol` 里既有 `fpack/chr/%s/` 也有 `chr/%s`：

```
DATA/files/chr/<code>/              <- 散装
DATA/files/fpack/chr/<code>/0000.fpk <- 打包
```

只改一处 ⇒ 另一条路径的旧模型还在。`swap_character.py` 两处都会改；
若是手工操作漏了一处，用 `verify_swap.py` 一眼就能看出来（它会分别报
散装区和 FPK 的检查结果）。

## 3. 「某个形态 / 某套配色还是原角色」

原因是**来源角色缺少对应文件**。例如来源没有 `0002.brres`，
而目标有，那么第三形态就会保留目标的原模型。

构建脚本会明确报出来：

```
WARN   0002.brres        slot has it, source does not -> stays the ORIGINAL character
```

这是**缺素材，不是替换失败**。想彻底解决只能给来源角色补上对应的模型文件
（超出本流程范围）。

## 4. 「进战斗崩溃 / 模型消失 / 模型扭成一团」

几乎一定是**动了不该动的文件**：

- 覆盖或修改了 `0000.mot`（动画）或 `0000.seq`（招式逻辑）；
- 整文件覆盖了 `.brres`（骨架不同，见第 7 节）；
- 把 `eft/chr/<code>/*.brres`（特效模型）当成外观文件一起换了。

处理：**回到原始树重做**。这些文件必须与原始版逐字节相同，用下面的命令确认：

```powershell
python scripts\verify_swap.py --out <mod树> --slot <T> --source <S> --game-root <原始树>
```

它会单独检查 `0000.mot` / `0000.seq` 是否仍等于原始版，
以及 FPK 里的非外观条目是否未被改动。

## 5. 「游戏提示无效读取 / 弹出错误窗口」

```
从 0x00000050 读取无效，PC=0x8034c87c（可能不止一条）
```

**这是无害误报，实测游戏完全正常运行。** 直接无视。

**不要为此启用 Dolphin 的 MMU**：它会显著拖慢速度，甚至真的卡住进不去。

## 6. 「FPK 解不开 / 游戏拒绝载入」

- 只用本仓库的 `fpk_tool.py` 打包。第三方工具可能写出不同布局的包。
- 先自检：

  ```powershell
  python scripts\fpk_tool.py roundtrip <原版.fpk>
  ```

  原版包必须 `ROUNDTRIP PASSED`。这一步通过，说明编解码器没问题，
  那么问题在构建流程，而不是格式。
- 用 `python scripts\fpk_tool.py list <mod树>\...\0000.fpk` 对比条目表：
  条目数、名称、顺序都应与原版一致，只有被替换条目的 `usize` 变了。

## 7. 「为什么不能直接把 .brres 整个复制过去？」

因为每个角色的骨架都不一样（实测骨骼数 46 ~ 172），而且**骨骼编号虽然共享，
排列顺序却不同**：

```
krn  78 根骨骼
hnt 106 根骨骼
共享骨骼编号 35 个 —— 其中只有 1 个落在相同的位置上
```

`.mot` 动画是按这套共享编号寻址骨骼的，所以：

- 用 T 的动画 + S 的**网格/贴图** ⇒ 编号对得上，正常显示（本方案）；
- 用 T 的动画 + S 的**整个模型文件** ⇒ 动画去驱动错误的骨骼，模型消失或崩溃。

现场验证：

```powershell
python scripts\brres_bones.py <T>\0000.brres <S>\0000.brres
```

## 8. 「要不要担心塞不下？」

**不用。** PS2 / PSP 的方案要在固定位置原位写回，才有容量上限；
本作的角色数据是独立的 FPK 文件，我们**整个重建**它，
来源比目标大多少都无所谓，原始镜像也完全不参与。
详见 [`measured-data.md`](measured-data.md) 第 6 节。

## 9. 干净重来

```powershell
Remove-Item <mod树> -Recurse -Force
Remove-Item <工作目录>\.work -Recurse -Force   # 顺手清掉 FPK 解包缓存
```

然后重跑 `swap_character.py`。原始树 `game_root` 从不修改，所以永远可以重来。
