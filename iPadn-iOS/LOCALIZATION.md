# 界面本地化（String Catalog）

iPadn 的界面文案由两个 String Catalog 管理：

- `iPadn/Resources/Localizable.xcstrings`：界面与错误文案
- `iPadn/Resources/InfoPlist.xcstrings`：`Info.plist` 里的用户可见文案（本地网络授权、IPA 文档类型）

源语言是简体中文（`zh-Hans`），目前提供阿拉伯语（`ar`），整套界面已翻译。

## 三条规则

1. **能交给 SwiftUI 的字面量保持原样。**
   `Text("下载")`、`Label("安装设置", systemImage:)`、`Button("添加")`、`Section("维护")`、`Toggle("专业模式", isOn:)`、`Picker("外观", …)`、`.navigationTitle("设置")`、`.alert("无法添加", …)`、`.accessibilityLabel("清空输入")`、以及 App Intents 的 `LocalizedStringResource` 都接收 `LocalizedStringKey`，字面量本身就是查表键。

2. **动态字符串用 `String(localized:)`。**
   计算属性、错误文案、`String?`、三元表达式、拼接、以及传进 `String` 形参的自定义组件（`PageHeader(title:)`、`EmptyState`、`RowCapsule`、`rootTabBar`、`actionConfirmation`、`sectionTitle`、`TagBadge(text:)`、`InfoStripItem(caption:)`）都不会自动本地化：

   ```swift
   store.infoMessage = String(localized: "已清除缓存")          // 键 = 中文原文
   Text(String(localized: "共 \(count) 个结果"))                // 键 = 共 %lld 个结果
   ```

   插值占位符：`Int` → `%lld`，`String` → `%@`。不确定类型时先转成字符串（例如 `\(String(status))`），避免猜错占位符导致查表失败、静默回退中文。

3. **不该翻译的内容用 `Text(verbatim:)`，逻辑值不要翻译。**
   JSON / HTML 样例、Bundle ID、URL 模板、枚举的 `rawValue`（例如 `DownloadFilter` 的值仍为中文，`title` 才做翻译）、版本号哨兵值（`未知版本`）都保持原样。

## 新增键

1. 按上面三条写好文案。
2. Xcode 打开工程会把新键抽取进 `Localizable.xcstrings`；也可以手工添加（键必须是中文原文）。
3. 填译文，状态设为 `translated`。
4. 在 `iPadn-iOS` 目录运行：

   ```bash
   python3 scripts/check_localization.py                 # 覆盖率
   python3 scripts/check_localization.py --missing       # 只列出缺失的键
   python3 scripts/check_localization.py --strict iPadn/Views/SearchView.swift
   ```

   校验内容：Catalog 是合法 JSON、`sourceLanguage` 是 `zh-Hans`、每条译文都标记 `translated`、译文占位符数量与键一致、`String(localized:)` 的键都存在、指定文件里可自动本地化的字面量都有条目。扫描会跳过注释，并正确解析字符串插值（含插值里的嵌套字符串）。

## 新增语言

1. 在两个 `.xcstrings` 里加语言（Xcode：选中文件 → 右侧 `+`）。
2. 在 `scripts/generate_project.py` 的 `knownRegions` 里加同样的语言代码；工程文件由脚本生成，也可以只改 `project.pbxproj`。
3. 跑一遍 RTL 清单（见下）。

## RTL 检查清单

- 方向性图标用语义名称：`chevron.forward`、`arrow.up.forward.square`，不要 `chevron.right`、`arrow.up.right.square`。
- 只用 `leading` / `trailing`，不要 `left` / `right`。
- 列表分隔符不要写死 `、`，用 `ListFormatter.localizedString(byJoining:)`。
- 数字、日期、货币跟随界面语言（不要写死 `Locale(identifier:)`）；`NumberFormatter` / `DateFormatter` 用 `Locale.current`。
- 阿拉伯语复数有 6 种形式，计数文案用 `xcstrings` 的 plural variation（见 `%lld 个结果`）。
- 阿拉伯语字体基线不同：最大辅助字号下重新检查行高、按钮宽度和截断。
- 自绘手势（`RevealMotion`）、价格图表、`MarqueeText` 需要真机确认镜像后仍正确。

## 未翻译（有意保留）

- `App/ToolIntents.swift` 的两个参数摘要 `搜索 \(\.$query)`、`导入 \(\.$file)`：App Intents 的参数占位符格式与普通字符串不同，留给 Xcode 抽取后确认；`AppShortcut` 的短语同理。
- `PurchaseExport` 导出的 CSV 表头与状态值（`在售 / 已下架 / 未检查`）：导出文件格式保持稳定。
- `WatchService` 从 GitHub Release 正文里过滤的 `验证：` 前缀、`AppUpdateService` 的构建信息行：解析上游中文文案用，不面向界面。
- 少量调试/演示数据（`--visual-preview` 的示例应用名）已翻译，但仅供预览。
