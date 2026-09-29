# Шаблон письма клиенту — Continuity / $990

**Кому:** decision maker (ecom / performance / CTO агентства)  
**От:** alex555196@gmail.com  
**Тема:** Content API sunset → Merchant API за 48 часов (фикс $990)

---

Здравствуйте, {Имя}!

Google отключил Content API for Shopping. Если каталог обновлялся прямыми вызовами `shoppingcontent.googleapis.com`, листинги в Google Shopping могли перестать обновляться — часто это выглядит как «магазин работает, а Shopping просел».

**Что делаю за фикс $990 / 48 часов с старта:**

1. Аудит: какие вызовы у вас реально ломаются  
2. Конвертация фида в Merchant API (ID, micros-цены, enum availability/condition — без float)  
3. Dry-run отчёт: ok / failed / warnings по вашим данным  
4. Staging upload в ваш API data source + выборочная сверка через `products.get`  
5. Короткий handoff: как повторять delta-upload сами  

**Не входит в $990** (оценю отдельно, если нужно): перепись `customBatch` в вашем коде, accounts/shipping settings APIs, экзотические атрибуты вне стандартного product feed.

Чтобы стартовать, ответьте тремя строками:

- платформа (Shopify custom / Magento / свой backend / агентство)  
- примерно сколько SKU  
- уже видите `410 Gone`? (да/нет)

Могу созвониться на 15 минут или сразу запросить sample feed (10–20 товаров) для dry-run без доступа к бою.

— Александр  
alex555196@gmail.com
