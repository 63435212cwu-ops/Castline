# 核实：审计第 7 条（`claimType` 不当）**不产生用户可见影响**

**版本**：`aee4c99808674e4220ab0104`

---

## 一、审计的说法

> 第 7 条：`ev_q2v_c659355_suppress_buddhism` — **claimType 不当**。
> 引文是地书传书『【好景不长，不到百年，朝廷就开始灭佛…】』，
> ctx 标明出自『【四：…』即四号传书，**属角色之言，标 narrator_fact 不当**。

**我核实：这条缺陷**成立**（数据层面）。**

## 二、而且它**不是孤例** —— 我校准出了规模

```
引文以「【」开头的事件（地书传书格式，即角色之言）: 401 条
  它们的 claimType 分布：
     character_claim  354   ← 多数标对了
     narrator_fact     15   ← **同型错误**
     protagonist_guess  7
     deception          4
     None              25
```

**⇒ **15 条**把"角色传书"标成了 `narrator_fact`，而同类引文有 **354 条**标的是 `character_claim`
⇒ **口径不一致，15 条是少数派，可判定为错标。**（审计只举了 1 条，我补出了全量 15 条。）**

## 三、但**产品不读这个字段** —— 我逐层核到了

```
$ grep -rn 'claimType' js/ --include=*.js | wc -l
0
```

**⇒ `claimType` 在 `js/` 下出现 **0 次**，任何界面都不读它。**

## 四、我一度怀疑"另一个必填字段缺失" —— 结果**自我推翻**

我发现**全部 17,705 个事件的 `basis` 都是 `None`**，而 `basis` **是产品真正读的**：
```js
// js/sky/sky-model.js:301-308
function narrativeBasis(v){ ... else code='unverified'; return {code, label: BASIS_LABEL[code]}; }
```
**⇒ 若 `basis` 缺失导致所有事件显示「未核验」，那才是**严重的用户可见问题**。**

**于是我复刻了 `evidenceStatus` 的**分支顺序**逐条算**（`js/atlas/atlas-source.js:913`）：
```js
if (entity && (derived||inferred||basis==='inference')) code='inference';
else if (quotes.length && verified===quotes.length && entity.verified!==false) code='verified';   ← **先走这里**
else if (quotes.length) code='quoted';
else if (!entity || basisCode==='unverified' ...) code='unverified';                            ← basis 只在这里用
else code='synthesis';
```

**实测分布**：
| 显示状态 | 条数 | 占比 |
|---|---:|---:|
| **原文已核验** | **16,869** | **95.3%** |
| 有引文未核验 | 798 | 4.5% |
| 归纳 | 38 | 0.2% |

**⇒ 「引文已核验」这一分支**在 `basis` 之前**判定，
所以 `basis=None` **不影响** 95.3% 的事件显示；只有**没有引文**的事件才会落到 `basis` 那一层。**

## 五、结论

| 项 | 判定 |
|---|---|
| 审计第 7 条（`claimType` 不当） | ✅ **数据层面成立**，且我补出**全量 15 条**（非孤例） |
| 它的**用户可见影响** | ❌ **无** —— `claimType` 在 `js/` 下出现 0 次 |
| 我怀疑的 `basis=None` | ❌ **不成立** —— `evidenceStatus` 先判引文，95.3% 显示「原文已核验」 |
| **严重性** | **低**：属字段一致性/口径问题，不是用户可见缺陷 |

**⇒ 我把这一条从"待修的语义缺陷"降级为"字段口径不一致（低危）"，
并给出规模（15 条）与依据（354 : 15）。**

## 六、沉淀规则（第 42 条）

> **"数据层面的错误"与"用户可见的错误"必须分开定级 —— 而判定方法是**读产品路径**，不是读数据。**
> 审计把 `claimType` 报为缺陷，**数据上它确实错了**；
> 但 `grep -rn 'claimType' js/` = **0 次** ⇒ **它永远不会显示给用户**。
> **而我随即产生的第二个怀疑（`basis=None` 导致全部显示"未核验"）也被产品路径推翻** ——
> 因为 `evidenceStatus` **先判引文再判 basis**，95.3% 走的是前一个分支。
> **⇒ 两次都靠"读消费端"定级，而不是靠"读数据"猜测影响。**
