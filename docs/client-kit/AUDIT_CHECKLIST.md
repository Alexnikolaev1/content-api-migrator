# Client kit — Continuity ($990 / 48h)

Чеклист аудита перед миграцией Content API → Merchant API.

## 1. Подтвердить, что это ваш кейс

- [ ] Код (ваш или агентства) бьёт в `shoppingcontent.googleapis.com`
- [ ] Нет «магического» приложения Shopify Google & YouTube / аналога, которое уже мигрировало
- [ ] Есть `410 Gone` или просадка показов/кликов в Google Shopping
- [ ] Есть доступ к Merchant Center и GCP/OAuth проекта

## 2. Снять слепок текущего фида

- [ ] Экспорт/дамп текущих product payloads (JSON массив)
- [ ] Зафиксировать число SKU
- [ ] Отметить кастомные поля (custom attributes, shipping overrides, salePrice)
- [ ] Прогнать локально: `migrate.ps1 dry-run feed.json --account-id ID`

## 3. Merchant API prerequisites

- [ ] Создан **API** primary (или supplemental) data source
- [ ] Имя вида `accounts/{ACCOUNT}/dataSources/{ID}` сохранено
- [ ] OAuth / service account со scope `https://www.googleapis.com/auth/content`
- [ ] Тестовый insert 1 SKU с `--limit 1 --verify` успешен

## 4. Staging

- [ ] Full dry-run: 0 FAIL (WARN допустимы, но разобраны)
- [ ] Upload staging data source с `--state` + `--delta`
- [ ] Выборочная сверка цен micros и availability в UI Merchant Center
- [ ] Нет массовых disapprovals после обработки (подождать несколько минут)

## 5. Cutover

- [ ] Согласован window (низкий трафик)
- [ ] Боевой data source / переключение ownership при необходимости
- [ ] Resume-файл и отчёт upload сохранены
- [ ] Мониторинг Shopping 24–48h после cutover

## Вне scope $990 (отдельная оценка)

- Перепись `customBatch` → parallel/async в клиентском коде
- Accounts / shippingsettings / local inventory sub-API
- Нестандартные атрибуты вне покрытого конвертера
