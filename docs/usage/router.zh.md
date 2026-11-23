# 理解路由

通常来说，每个 RSS 消息来源都有一个订阅链接。以卫报世界新闻为例，它的订阅链接是 [www.theguardian.com/world/rss](https://www.theguardian.com/world/rss)。在这个订阅链接中，第一个斜线 `/` 前的部分被称作域名（domain），即 `www.theguardian.com`；其后的部分被称作路由（route），即 `/world/rss`。你可以将一个订阅链接想象成一条路线，其中域名是大致的地址，而路由则具体到具体某楼某单元某层某室：有了订阅链接，你就可以循着它在互联网上找到你所需要的资源。

!!!note
    这里对订阅链接的定义并不完全符合 [URL](https://en.wikipedia.org/wiki/URL) 标准。文档对此作了一定的简化，方便无技术背景的读者理解。

## 实例与路由

在实例地址后加上 `/all_routes`，即可查看已启用的订阅、参数说明和示例链接。

如果你希望通过 RSSerpent 来订阅一些不支持 RSS 的网站，那么同理 —— 你也需要找到对应资源的订阅链接。对于 RSSerpent 来说，订阅链接同样分成域名与路由两部分：

- 每个域名都对应着一个 RSSerpent 实例，例如官方域名 [rsserpent.imciel.com](https://rsserpent.imciel.com) 就对应着官方实例。你可以在[[部署]](../deployment/index.md)页面上找到一些官方实例，但我们更推荐你自建实例以满足你个人变化而多样的需求。
- 默认情况下，RSSerpent 实例不装载任何路由。实例的维护者需要通过[[安装插件]](../deployment/plugin.md)来为实例装载路由。如果你在使用某个他人的实例时发现缺少了你需要的插件或路由，你可以向实例维护者提出申请，或者选择自建实例。

!!!note
    实例是指一份正在运行中的 RSSerpent 软件体。

!!!note
    每个 RSSerpent 插件都包含一个或多个路由。

RSSerpent 的[官方实例](https://rsserpent.imciel.com)上装载了哔哩哔哩[插件](https://github.com/RSSerpent-Rev/rsserpent-plugins/tree/main/rsserpent_plugins/bilibili)。因此，你可以在官方实例上使用路由 `/bilibili/user/{uid}/video` 来订阅某个用户发布的视频。例如，如果你希望订阅 [Chubbyemu](https://www.youtube.com/channel/UCKOvOaJv4GK-oDqx-sj7VVg) 在哔哩哔哩的官方[中文翻译频道](https://space.bilibili.com/297786973)，那么通过拼接官方实例的域名 `rsserpent.imciel.com` 与路由 `/bilibili/user/297786973/video` 你可以得到如下订阅链接：

![RSSerpent Bilibili Chubbyemu](https://cdn.jsdelivr.net/gh/rsserpent/asset@latest/rsserpent-bilibili-chubbyemu.png)

## 路由参数

!!!warning
    本章文档剩余内容中的任何示例仅供参考，不保证在任何实例上真实可用。

在上面的例子中，我们注意到，部分路由并不是完整的，需要你填写某些信息才能正常工作。举例来说，假设这个路由能够帮助你订阅某个用户发布的视频，但它却无法知道用你希望订阅的具体是*哪个*用户 —— 这时就需要你来填写部分**路由参数**。有了这些参数作为输入，路由才能完整正常地工作。

路由参数一般被花括号 `{}` 包裹，在实际填写时，你应该去掉这对花括号。不同的路由是由不同的插件来提供的，一般来说，你可以在相关插件的文档页面找到各个路由参数的含义、以及你应该如何去获取并填写这些参数。

以路由 `/bilibili/user/{uid}/video` 为例，该路由接受一个路由参数 `uid`。每个哔哩哔哩用户都具有一个唯一标识码（即 ID），你通常可以在用户主页的地址中找到这个唯一标识码。通过这个唯一标识码，路由才能找到该用户发布的视频，并将视频列表输出为订阅链接供你订阅。

## 查询参数

路由参数是必填的。但有时候，有些路由还需要接受一些选填的、可变的、有条件的参数 —— 这些参数被称为**查询参数**：

- 查询参数应置于路由尾部，以 `?` 问号与路由主体隔开；
- 查询参数可以有任意多个，每个形如 `{name}={value}`；
- 查询参数之间以 `&` 隔开。

例如 `/bilibili/user/297786973/video?limit=5` 会把订阅限制为最多五个条目。各路由的专用参数见当前实例的 `/all_routes`。
# 请求限制

将 `rsserpent_rev.plugins.builtin` 加入[部署配置](../deployment/plugin.zh.md)的 `plugins` 列表，即可启用内置示例路由。按数量生成条目的示例最多生成 1,000 条。
每个正则过滤模式最多使用 512 个字符。每次请求最多用 50 毫秒过滤条目。
过滤条件无效或超过限制时，服务返回 HTTP 400。

普通路由默认返回 RSS，也可以通过 `.rss` 或 `.atom` 选择格式。
接收完整 URL 的路由保留其后缀，默认返回 RSS。用 `?format=atom` 选择 Atom。
上游 URL 带查询参数时，将它的查询分隔符编码为 `%3F`，使上游查询留在路径中。

标题、描述或分类缺失时，不满足包含条件，也不会命中排除条件。
日期过滤跳过没有日期的条目。`limit=0` 只返回订阅元数据。负数返回 HTTP 400。
