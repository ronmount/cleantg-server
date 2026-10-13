# Self hosting CleanTG Server

Это требования к будущему развёртыванию. Исполняемого сервиса и готовой команды `docker compose up` в драфте нет.

## Минимальная установка

Один API service, PostgreSQL и HTTPS reverse proxy. Public base URL может содержать prefix. Домен и сертификат должны доверяться всем подключаемым устройствам. Встроенный обязательный hosted-сервис или центральный аккаунт CleanTG не используется.

Серверу нужны исходящие HTTPS соединения к фиксированным Telegram OIDC endpoints при первом входе/повторной авторизации. Оператор создаёт свой Telegram bot, настраивает Login в BotFather, Allowed URLs, Client ID и Client Secret. Phone и разрешение писать от имени бота не требуются. Telegram API ID/hash и пользовательские auth keys не являются конфигурацией backend.

LAN/VPN deployment может держать сам API закрытым от Интернета, если браузер пользователя достигает зарегистрированного HTTPS callback и устройства доверяют сертификату. Совместимость выбранного домена/redirect URI с правилами BotFather надо проверить прототипом. Первая авторизация зависит от доступности Telegram; это не полностью автономная система без внешней сети.

## Конфигурация реализации

| Параметр | Назначение |
| --- | --- |
| PUBLIC_BASE_URL | Канонический HTTPS origin/prefix, фиксирует ссылки и проверку DPoP htu |
| INSTANCE_ID | Постоянный случайный UUID deployment, не меняется при обычном restart |
| DATABASE_URL | Secret, отдельная runtime role PostgreSQL |
| TELEGRAM_OIDC_CLIENT_ID | Bot/OIDC client оператора |
| TELEGRAM_OIDC_CLIENT_SECRET_FILE | Secret file; не попадает в образ/Git/логи |
| TOKEN_SIGNING_KEY_FILE | Собственный ключ CleanTG, с планом ротации kid |
| PIN_PEPPER_FILE | Secret вне БД и её backup |
| ISSUANCE_EPOCH_STORE | Монотонная эпоха выдачи вне откатываемого snapshot |
| LEASE_TTL_MS | Не более лимита, поддерживаемого клиентским протоколом; цель v1 5000 |
| RETENTION_* | Сроки очистки lease/агрегатов/audit |
| TRUSTED_PROXY_CIDRS | Какие reverse proxies могут задавать forwarded headers |

Сервис при старте отказывает для пустых/примерных секретов, не-HTTPS PUBLIC_BASE_URL, отсутствующей instance identity, неизвестной схемы БД или конфликта issuance epoch. Production data не инициализируется пустой БД при ошибке подключения.

## Наблюдаемость

Readiness проверяет соединение с БД, миграции, работоспособность clock guard и signing key. Liveness не должен объявлять готовность выдавать разрешения. Основные метрики: время lease-транзакции, lock contention, отказы quota, число активных устройств, KDF queue, rate-limit/replay rejects, outbox lag и clock anomaly. Метрики не маркируются Telegram ID или peer ID.

Предпочтительный кандидат доставки событий — WebSocket из PostgreSQL outbox. Reverse proxy должен поддерживать WSS/Upgrade, корректные idle timeouts и ограниченные очереди; целевые значения проверяются native PoC. Native клиенты проверяют lease независимо от доставки событий. Публикация APNs/FCM уведомлений для серверной синхронизации не нужна для корректности; фоновые устройства получают snapshot при возвращении в приложение. См. [статус протокола](realtime.md).

## Backup и upgrade

Backup включает БД и необходимые зашифрованные deployment secrets по отдельному защищённому процессу. Issuance epoch нельзя откатывать вместе с БД. До публичного запуска требуется проверенный restore runbook из `security.md`: старые токены/lease не должны снова становиться действительными, а дневной бюджет не должен увеличиваться из старого backup.

Миграции схемы проходят по отдельной роли и останавливают несовместимую выдачу lease. Клиент проверяет protocol major и advertised capabilities; при несовместимости сохраняет серверный режим и кэш, блокируя ограниченные чаты после expiry. Старый клиент не создаёт local fallback.

Удаление профиля и постоянное удаление backup — самостоятельные подтверждаемые операции будущего сервиса. Они не прячутся под кнопкой «отключить синхронизацию на устройстве».
