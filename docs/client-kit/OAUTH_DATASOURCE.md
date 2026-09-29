# OAuth и API data source (Merchant API)

Краткая инструкция для клиента / агентства. Scope: `https://www.googleapis.com/auth/content`.

## 1. Data source

В Merchant Center создайте data source с input type **API** (primary или supplemental).

Скопируйте resource name:

```text
accounts/123456789/dataSources/987654321
```

Только API/FILE datasource принимают `productInputs.insert`. Обычный «Google Sheets» feed сюда не подходит.

## 2. Авторизация — вариант A (быстрый токен)

1. Получите OAuth access token с scope `content` (OAuth Playground или ваш backend).
2. В PowerShell:

```powershell
$env:MERCHANT_ACCESS_TOKEN = "ya29...."
```

Токен короткоживущий — удобно для staging smoke-теста.

## 3. Авторизация — вариант B (service account)

1. GCP: создайте service account, скачайте JSON ключ.
2. В Merchant Center добавьте SA как пользователя с доступом к продуктам.
3. Укажите путь:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secrets\merchant-sa.json"
```

Инструмент сам возьмёт ADC через `google-auth`.

## 4. Первый боевой прогон (безопасно)

```powershell
# план без API
.\migrate.ps1 upload feed.json --account-id 123456789 --data-source accounts/123456789/dataSources/987654321

# 1 товар + verify
.\migrate.ps1 upload feed.json --account-id 123456789 --data-source accounts/123456789/dataSources/987654321 --yes --limit 1 --verify --state .migrate-state.json --report upload.txt
```

`--verify` делает `products.get` и сверяет offerId / language / feedLabel / availability / amountMicros.

## 5. Полный каталог

```powershell
.\migrate.ps1 upload feed.json --account-id 123456789 --data-source accounts/123456789/dataSources/987654321 --yes --state .migrate-state.json --delta --concurrency 4 --retries 5 --report upload-full.txt
```

- `--state` — resume после обрыва + хеши для delta  
- `--delta` — не грузить неизменённые SKU  
- `--concurrency` — параллельные insert (не ставьте десятки без нужды)  
- `--retries` — повторы на 429/5xx  

## Частые ошибки

| Симптом | Что проверить |
|---|---|
| 401/403 | scope `content`, доступ SA к аккаунту |
| 400 dataSource | не API datasource / чужой account id |
| verify failed | фид ещё обрабатывается — подождите и повторите get |
| HTTP 429 | снизьте `--concurrency`, увеличьте `--retries` |
