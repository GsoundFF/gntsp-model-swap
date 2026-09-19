# Changelog

## v1.0.0

首个版本。把三次手工成功制作（雏田 / 纲手 / 井野 替换夕日红）的流程
整理成可复用工具与 agent 技能。

- `swap_character.py`：把针对单个来源角色写死的构建脚本通用化为
  `--slot` / `--source` 参数；散装文件与 FPK 两处同时替换；
  支持 `model`（保留目标招式）与 `full`（整体移植）两种模式。
- `verify_swap.py`：交付前校验，覆盖散装文件、`0000.mot`/`0000.seq` 未改动、
  FPK 内条目分类、以及"仍等于原角色"的文件清单。
- `fpk_tool.py`：FPK 解包 / 重打包 / `roundtrip` 往返自检。
- `brres_bones.py`：定位 MDL0 骨骼字典，输出骨骼编号序列；
  两文件模式给出共享编号与顺序差异。
- `scan_characters.py`：全角色模型大小与骨骼数扫描。
- `references/`：角色代码、文件格式、实测数据、排错手册，
  以及三份原始成功流程记录。

### 已验证

- `fpk_tool.py roundtrip` 对原版 `krn/0000.fpk` 的 20 个子文件全部往返一致。
- `swap_character.py --slot krn --source hnt` 在原版树上重跑，
  复现了成功记录中的全部文件大小，FPK 精确得到 `1269088` 字节。
- `verify_swap.py` 对上述构建结果 30 项检查全部通过。
