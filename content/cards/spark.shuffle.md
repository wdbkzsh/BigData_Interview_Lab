---
knowledge_point_id: spark.shuffle
title: Shuffle
---

## 一句话定义

Shuffle 是 Spark 在 Stage 之间进行数据重分区和跨节点传输的过程。

## 核心原理

- Shuffle 是宽依赖（Wide Dependency）的物理表现
- 涉及磁盘 I/O、序列化、网络传输三个阶段
- ShuffleManager 负责管理 Shuffle 过程（默认 SortShuffleManager）
- SortShuffleManager 在内存不足时溢写磁盘，最后合并为一个文件

## 面试高频点

- SortShuffleManager 与 HashShuffleManager 的区别
- Shuffle Write 的三种实现：BypassMergeSort、Sort、Unsafe
- Shuffle 对性能的影响及优化手段
- repartition 和 coalesce 是否触发 Shuffle

## 常见易错点

- 混淆 Stage 划分依据：Shuffle Boundary 才是划分点，不是 RDD 转换类型
- 认为 coalesce 一定不触发 Shuffle：默认 shuffle=false 时通常用于减少分区且不发生 Shuffle；需要通过 Shuffle 重新分区时，应显式启用 shuffle，或使用 repartition
- 忽略 Shuffle Read 的拉取机制：由 Executor 直接拉取，不经过 Driver