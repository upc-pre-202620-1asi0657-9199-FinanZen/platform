# FinanZen Financial Records Service

Avance funcional del backend de FinanZen alineado con `PF-01`, `PF-02`, `QA-01`, `QA-02` y `QA-07` del diseño arquitectónico.

## Funcionalidades

- Registro idempotente de ingresos y egresos.
- Validación de importes, moneda, fecha, categoría y cuenta.
- Aislamiento de movimientos mediante el encabezado `X-User-Id`.
- Consulta de movimientos del usuario.
- Resumen mensual de ingresos, egresos y saldo.
- Persistencia local en SQLite.
- Especificación OpenAPI y Swagger generadas por FastAPI.

`X-User-Id` simula la identidad que posteriormente entregará Identity and Access Service. No constituye el mecanismo final de autenticación.

## Ejecución

```powershell
cd services/financial-records-service
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger estará disponible en `http://127.0.0.1:8000/docs`.

La interfaz web estará disponible en `http://127.0.0.1:8000`.

## Ejemplo

```powershell
$headers = @{
  'X-User-Id' = 'demo-user'
  'Idempotency-Key' = 'demo-income-0001'
}

$body = @{
  account_id = 'cash-account'
  type = 'income'
  amount = 1500.00
  currency = 'PEN'
  category = 'salary'
  occurred_at = '2026-10-01T10:00:00Z'
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8000/api/v1/transactions' `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body $body

Invoke-RestMethod `
  -Uri 'http://127.0.0.1:8000/api/v1/summary?month=2026-10' `
  -Headers @{ 'X-User-Id' = 'demo-user' }
```

## Pruebas

```powershell
python -m pytest -q
```
