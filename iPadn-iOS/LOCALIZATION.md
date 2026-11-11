# 界面本地化（String Catalog）

iPadn 的界面文案由 `iPadn/Resources/Localizable.xcstrings` 管理。源语言是简体中文（`zh-Hans`），当前已提供阿拉伯语（`ar`）作为 RTL 语言的试点。

## 三条规则

1. **能交给 SwiftUI 的字面量保持原样。**
   `Text("下载")`、`Label("安装设置", systemImage:)`、`Button("添加")`、`Section("维护")`、`Toggle("专业模式", isOn:)`、`Picker("外观", …)`、`.navigationTitle("设置")`、`.alert("无法添加", …)`、`.accessibilityLabel("清空输入")` 等位置接收的是 `LocalizedStringKey`，字面量本身就是查表键，不需要改代码。

2. **动态字符串用 `String(localized:)`。**
   计算属性、错误文案、`String?`、三元表达式、拼接、传进 `String` 形参的自定义组件（`PageHeader(title:)`、`EmptyState`、`RowCapsule`、`rootTabBar`、`actionConfirmation`）都不可能自动本地化：

   ```swift
   // 会静默回退成中文
   store.infoMessage = "已清除缓存"

   // 正确：键 = 中文原文
   store.infoMessage = String(localized: "已清除缓存")

   // 带插值：键是格式化串，翻译里必须保留占位符
   Text(String(localized: "共 \(count) 个结果"))   // 键：共 %lld 个结果
   ```

   插值占位符规则：`Int` → `%lld`，`String` → `%@`，`Double` → `%lf`。

3. **不该翻译的内容用 `Text(verbatim:)`。**
   JSON 样例、Bundle ID、URL 模板、SF Symbol 名称等。

## 新增键

1. 在 Swift 里按上面三条写好文案。
2. 用 Xcode 打开工程，编辑器会把新键抽取进 `Localizable.xcstrings`；也可以手工添加（键必须是中文原文）。
3. 填译文后把状态设为 `translated`。
4. 在 `iPadn-iOS` 目录运行校验：

   ```bash
   python3 scripts/check_localization.py                 # 输出覆盖率
   python3 scripts/check_localization.py --strict iPadn/Views/SearchView.swift
   ```

   校验内容：Catalog 是合法 JSON、每条译文都有 `translated` 标记、译文占位符数量与键一致、`String(localized:)` 用到的键都存在、指定文件里 SwiftUI 自动本地化的字面量都已在 Catalog 中。

## 新增语言

1. 在 `Localizable.xcstrings` 里加语言（Xcode：选中文件 → 右侧 `+` → 语言）。
2. 在 `scripts/generate_project.py` 的 `knownRegions` 里加同样的语言代码，然后手工或重新生成 `project.pbxproj`（工程文件由脚本生成）。
3. 阿拉伯语还需要 RTL 检查，见下节。

## RTL 检查清单

- 方向性图标要用语义名称：`chevron.forward` / `arrow.up.forward.square`，不要用 `chevron.right` / `arrow.up.right.square`。
- 只用 `leading` / `trailing`，不要用 `left` / `right`；`alignment: .leading` 会随方向镜像。
- 自绘布局、横向手势（`RevealMotion`）、图表坐标轴要真机确认镜像后仍然正确。
- 数字、日期、货币：避免写死 `Locale(identifier: "zh_CN")`（见 `PriceViews.swift`、`PriceService.swift`、`WatchService.swift`），改为跟随界面语言。
- 阿拉伯语复数有 6 种形式（zero / one / two / few / many / other），计数文案用 `xcstrings` 的 plural variation，不要用单一形式。
- 阿拉伯语不是拉丁字母：字号、行高、按钮宽度要在最大辅助字号下重新检查。

## 当前进度

- 已完成：搜索页、设置页及其共用的组件、搜索错误文案、图标切换相关文案，共 130 条。
- 未完成：其余页面仍为中文；`Info.plist` 的 `NSLocalNetworkUsageDescription`（首次启动的本地网络授权弹窗）与 `CFBundleTypeName` 还没本地化，需要 `ar.lproj/InfoPlist.strings`。
- 全量扫描剩余条目：`python3 scripts/check_localization.py --missing`。
