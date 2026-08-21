$ErrorActionPreference = "Stop"
$AppPort = 8001

$listeners = Get-NetTCPConnection -LocalPort $AppPort -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    $owners = $listeners |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            Get-Process -Id $_ -ErrorAction SilentlyContinue |
                Select-Object Id, ProcessName
        }

    Write-Error (
        "Port $AppPort is already reserved by: " +
        (($owners | ForEach-Object { "$($_.ProcessName) (PID $($_.Id))" }) -join ", ")
    )
    exit 1
}

Write-Host "Reserving http://127.0.0.1:$AppPort for LDP Learning Portal..."
docker compose up --build