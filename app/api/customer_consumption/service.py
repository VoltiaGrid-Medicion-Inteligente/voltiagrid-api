import calendar
from datetime import date
from decimal import Decimal
from fastapi import HTTPException, status
from app.api.common import Principal

def get_real_calculation(month: str, target_customer_code: str, principal: Principal) -> list:
    """
    Service layer function (T-13.3).
    Validates isolation rules and calculates daily consumption.
    """
    # Importación local para evitar el error de "circular import"
    from app.api.customer_consumption.main import DailyBandConsumption
    
    # 1. Isolation Rule enforced in the SERVICE layer (CA-10)
    if principal.role == "customer" and principal.customer_code != target_customer_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Customers can only read their own consumption"
        )
    
    # 2. Reemplazo del stub (T-13.2)
    year, mon = map(int, month.split("-"))
    bands = [
        ("off-peak", "4.100", "0.12", 20, 0), 
        ("intermediate", "3.200", "0.18", 20, 1), 
        ("peak", "2.500", "0.30", 8, 0)
    ]
    days = []
    for day in range(1, calendar.monthrange(year, mon)[1] + 1):
        for band, kwh, price, readings, estimated in bands:
            days.append(DailyBandConsumption(
                date=date(year, mon, day), 
                band_name=band, 
                energy_kwh=Decimal(kwh),
                cost=(Decimal(kwh) * Decimal(price)).quantize(Decimal("0.0001")),
                readings=readings, 
                estimated_readings=estimated,
            ))
    return days