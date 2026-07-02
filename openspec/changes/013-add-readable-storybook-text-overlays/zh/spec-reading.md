# 中文 Spec Reading：013 Readable Storybook Text Overlays

## 1. 这个 spec 解决什么问题

012 已经把图片放进 Keynote，并且改成 full-bleed：

```text
图片铺满整页
文字叠在图片上
```

但现在还有一个明显问题：

```text
文字是否看得清？
```

013 就是解决这个问题。

它处理：

- 自动检测图片背景亮度。
- 自动选择白色/深色文字。
- 判断是否需要半透明文字底板。
- 尝试选择更适合放文字的位置。
- 支持多种绘本文字 overlay 模板。

## 2. 不做什么

013 不做：

- 不生成图片。
- 不调用 LLM。
- 不调用视觉模型。
- 不改 DeckSpec。
- 不做印刷 bleed / CMYK / 裁切线。
- 不替换 Keynote。

它只是让：

```text
DeckSpec + 图片 assets -> Keynote
```

这个阶段的文字更清楚。

## 3. 新增模块

建议新增：

```text
src/open_keynote_agent/renderers/overlays.py
```

这个模块只做纯计算：

```text
SlideSpec + image_path -> OverlayPlan
```

不要在这里调用 Keynote。

不要在这里调用 LLM。

## 4. OverlayPlan

建议有这些结构：

```python
OverlayRegion:
    name
    x
    y
    width
    height

OverlayStyle:
    text_color
    font_size
    use_backing
    backing_color
    backing_opacity
    shadow

OverlayPlan:
    slide_index
    region
    style
    text
    diagnostics
```

`text_color` 用：

```text
#FFFFFF
#2C1810
```

## 5. 候选文字区域

不要只固定一个位置。

至少准备四个区域：

```text
bottom_band
top_band
left_panel
right_panel
```

可以再加：

```text
center_caption
```

所有坐标仍然使用 Keynote 1280x720：

```text
bottom_band:
  x=90
  y=500
  width=1100
  height=170

top_band:
  x=90
  y=50
  width=1100
  height=150

left_panel:
  x=70
  y=120
  width=430
  height=480

right_panel:
  x=780
  y=120
  width=430
  height=480
```

## 6. 图片亮度检测

用 Pillow 读取图片。

把 Keynote 坐标映射到图片像素坐标。

对每个候选区域裁剪图片，然后计算平均亮度。

亮度公式：

```text
Y = 0.2126 * R + 0.7152 * G + 0.0722 * B
```

规则：

```text
背景暗 -> 白字 #FFFFFF
背景亮 -> 深棕字 #2C1810
```

建议阈值：

```text
mean_luminance < 128 -> #FFFFFF
mean_luminance >= 128 -> #2C1810
```

## 7. 图片复杂度 / busy score

只看平均亮度不够。

如果图片区域很花、很多细节，文字也会看不清。

MVP 可以用亮度标准差作为 busy score：

```text
stddev_luminance 越高，区域越复杂
```

如果区域太复杂：

```text
use_backing = True
```

## 8. 半透明底板

理想效果：

```text
图片
半透明底板
文字
```

但是 Keynote AppleScript 对 shape fill / opacity 可能不稳定。

所以 MVP 可以这样：

- OverlayPlan 里先标记 `use_backing=True`。
- 如果当前 Keynote 工具不能可靠生成底板，不要失败。
- 仍然用自动选择的文字颜色渲染文字。

后续可以做一个更稳的方法：

```text
用 Pillow 生成一张半透明 PNG 底板
再用 keynote.add_image 插进去
```

## 9. 阴影 / 描边

文字阴影和描边很有用。

但 Keynote AppleScript 未必稳定。

013 可以先在 plan 中表达：

```text
shadow=True
```

如果不能发出实际 Keynote 操作，不要失败。

## 10. 区域选择

对每个候选区域打分：

```text
score =
  busy_score
  + center_subject_penalty
  + slide_kind_preference_penalty
```

分数最低的区域用于放文字。

不同 slide kind 可以有偏好：

- cover：偏向 bottom 或 center_caption。
- chapter/content：偏向 bottom。
- climax：如果 bottom 太复杂，偏向 top。
- lesson：偏向 left_panel / right_panel。
- ending：偏向 bottom 或 center_caption。

这仍然是确定性规则，不是 LLM 决策。

## 11. Renderer 集成

012 当前顺序是：

```text
add_image full-bleed
add_text_box overlay
```

013 保持这个顺序。

只是在 `add_text_box` 前先做：

```python
plan = build_overlay_plan(slide, image_path)
```

然后：

```text
keynote.add_text_box(
  x=plan.region.x,
  y=plan.region.y,
  width=plan.region.width,
  height=plan.region.height,
  font_color=plan.style.text_color,
)
```

## 12. 失败 fallback

如果图片打不开、Pillow 不可用、分析失败：

不要让整个 render 失败。

回退到 012 固定 overlay：

```text
x=90
y=500
width=1100
height=170
```

并使用默认文字颜色。

## 13. 测试重点

必须测试：

- 亮背景选择深色文字。
- 暗背景选择白色文字。
- 复杂背景要求 backing。
- 多个候选区域中选择更不复杂的区域。
- 图片分析失败时 fallback。
- renderer 里图片先插入，文字后插入。
- `font_color` 传给 `keynote.add_text_box`。
- 没图片时旧 fallback 不变。

## 14. 一句话总结

012 负责：

```text
把图放进去，全屏，文字叠上去
```

013 负责：

```text
让叠上去的文字看得清、位置更合理
```
