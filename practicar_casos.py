import os
import sys
import re
import math
from decimal import Decimal
from datetime import datetime

# Añadir directorio actual al PATH de python para importar app
sys.path.append(os.getcwd())

from app.core.cfg_database import engine
from app.repositories import repo_creditos
from sqlalchemy import text

# Ruta al archivo de casos
CASOS_MD = "../PDFS/ENUNCIADOS_30_CASOS_CREDITO_EMPRESARIAL.md"

def limpiar_texto(text):
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        l = line.strip()
        if not l:
            cleaned_lines.append("")
            continue
        # Saltear números de página "X / Y"
        if re.match(r"^\d+\s*/\s*\d+$", l):
            continue
        # Saltear nombre del documento
        if "ENUNCIADOS_30_CASOS_CREDITO_EMPRESARIAL.md" in l:
            continue
        # Saltear fecha de cabecera
        if l == "2026-06-12":
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def parsear_casos():
    if not os.path.exists(CASOS_MD):
        print(f"Error: No se encontró el archivo de casos en {CASOS_MD}")
        sys.exit(1)
        
    with open(CASOS_MD, "r", encoding="utf-8") as f:
        text_content = f.read()
        
    cleaned_text = limpiar_texto(text_content)
    
    # Dividir por "Caso " con o sin "##"
    cases_raw = re.split(r"(?:##\s+)?Caso\s+", cleaned_text, flags=re.IGNORECASE)
    
    parsed_cases = []
    for index, raw in enumerate(cases_raw[1:], start=1):
        raw_clean = re.sub(r"\s+", " ", raw)
        
        # Regex para extraer datos
        monto_match = re.search(r"préstamo de \*\*S/\s*([0-9,]+)\*\*", raw_clean)
        cliente_match = re.search(r"cliente \*\*([^*]+)\*\*", raw_clean)
        desembolso_match = re.search(r"desembolsa el \*\*([0-9]{2}-[0-9]{2}-[0-9]{4})\*\*", raw_clean)
        plazo_match = re.search(r"plazo de \*\*([0-9]+)\s*meses\*\*", raw_clean)
        tea_match = re.search(r"Tasa Efectiva Anual \(TEA\) de \*\*([0-9.]+)\s*%?\*\*", raw_clean)
        seguro_match = re.search(r"(con|sin) seguro de desgravamen", raw_clean)
        dia_pago_match = re.search(r"\*\*([0-9]+) de cada mes\*\*", raw_clean)
        cuota_match = re.search(r"Cuota mensual:\s*S/\s*([0-9.,]+)", raw_clean)
        
        if monto_match and cliente_match and desembolso_match and plazo_match and tea_match and seguro_match and dia_pago_match and cuota_match:
            parsed_cases.append({
                "id": index,
                "monto": float(monto_match.group(1).replace(",", "")),
                "cliente": cliente_match.group(1).strip(),
                "desembolso": desembolso_match.group(1),
                "plazo": int(plazo_match.group(1)),
                "tea": float(tea_match.group(1)),
                "con_seguro": seguro_match.group(1) == "con",
                "dia_pago": int(dia_pago_match.group(1)),
                "cuota": float(cuota_match.group(1).replace(",", ""))
            })
            
    return parsed_cases

# Mapeo de nombres simplificados de casos a criterios de búsqueda en BD
CLIENT_MAPPING = {
    "Castor Pérez": ("Pérez", "Castor"),
    "Eneida Mamani": ("Mamani", "Eneida"),
    "Ovidio Torres": ("Torres", "Ovidio"),
    "Dante Flores": ("Flores", "Dante"),
    "Laura Mendoza": ("Mendoza", "Laura"),
    "Boccaccio Vargas": ("Vargas", "Boccaccio"),
    "Orlando Ríos": ("Ríos", "Orlando"),
    "Gerusalemme Huanca": ("Huanca", "Gerusalemme"),
    "Pedro Calderón": ("Calderón", "Pedro"),
    "Félix Chávez": ("Chávez", "Félix"),
    "Hildegarda Huanca": ("Huanca", "Hildegarda"),
    "Stendhal Aguilar": ("Aguilar", "Stendhal"),
    "Kipling Soto": ("Soto", "Kipling"),
    "Erinná Espinoza": ("Espinoza", "Erinná"),
    "Annie Espinoza": ("Espinoza", "Annie"),
    "Homero Quispe": ("Quispe", "Homero"),
    "Virgilio Mamani": ("Mamani", "Virgilio")
}

def buscar_cliente_bd(conn, name_key):
    search_terms = CLIENT_MAPPING.get(name_key)
    if not search_terms:
        # Fallback a buscar por palabras
        parts = name_key.split()
        if len(parts) >= 2:
            search_terms = (parts[0], parts[1])
        else:
            search_terms = (name_key, "")
            
    sql = text("""
        SELECT pkcliente, nomcliente, codcliente 
        FROM dcliente 
        WHERE nomcliente ILIKE :term1 AND nomcliente ILIKE :term2
        LIMIT 1
    """)
    res = conn.execute(sql, {"term1": f"%{search_terms[0]}%", "term2": f"%{search_terms[1]}%"}).mappings().first()
    return res

def mostrar_cabecera():
    os.system('clear')
    print("=" * 70)
    print("  SIMULADOR Y EVALUADOR INTERACTIVO DE CRÉDITOS EMPRESARIALES  ")
    print("                      BANCO DE LA NACIÓN                       ")
    print("=" * 70)

def main():
    cases = parsear_casos()
    
    while True:
        mostrar_cabecera()
        print(f"Se cargaron exitosamente {len(cases)} casos del archivo MD.")
        print("\n[1] Listar todos los casos")
        print("[2] Practicar un caso específico (Registrar -> Evaluar -> Desembolsar)")
        print("[3] Salir")
        
        opc = input("\nSeleccione una opción: ").strip()
        
        if opc == "1":
            mostrar_cabecera()
            print(f"{'Caso':<6} | {'Cliente':<25} | {'Monto':<10} | {'Plazo':<6} | {'TEA':<8} | {'Seguro':<7} | {'Cuota MD':<10}")
            print("-" * 80)
            for c in cases:
                seg_str = "Sí" if c["con_seguro"] else "No"
                print(f"{c['id']:<6} | {c['cliente']:<25} | S/ {c['monto']:<7,.0f} | {c['plazo']:<4}m | {c['tea']*100:.2f}% | {seg_str:<6} | S/ {c['cuota']:<10.2f}")
            input("\nPresione Enter para volver al menú...")
            
        elif opc == "2":
            num_str = input("\nIngrese el número de caso a practicar (1-30): ").strip()
            if not num_str.isdigit() or not (1 <= int(num_str) <= len(cases)):
                print("Número de caso inválido.")
                input("\nPresione Enter para continuar...")
                continue
                
            case_id = int(num_str)
            case = next(c for c in cases if c["id"] == case_id)
            
            mostrar_cabecera()
            print(f"--- DETALLES DEL CASO {case['id']} ---")
            print(f"Cliente:             {case['cliente']}")
            print(f"Monto Solicitado:    S/ {case['monto']:,.2f}")
            print(f"Plazo (Meses):       {case['plazo']}")
            print(f"TEA:                 {case['tea'] * 100:.2f}%")
            print(f"Seguro Desgravamen:  {'SÍ' if case['con_seguro'] else 'NO'}")
            print(f"Fecha Desembolso:    {case['desembolso']}")
            print(f"Día de pago mensual: {case['dia_pago']}")
            print(f"Cuota mensual en MD: S/ {case['cuota']:,.2f}")
            print("-" * 50)
            
            # 1) Math Sim
            tea_val = Decimal(str(case['tea']))
            tem_val = Decimal(math.pow(1 + float(tea_val), 1/12.0) - 1)
            monto_val = Decimal(str(case['monto']))
            plazo_val = case['plazo']
            
            cuota_calc = monto_val * (tem_val * Decimal(math.pow(1 + float(tem_val), plazo_val))) / (Decimal(math.pow(1 + float(tem_val), plazo_val)) - 1)
            cuota_calc = round(cuota_calc, 2)
            
            print(f"Cálculo matemático local:")
            print(f"-> TEM Calculada:    {tem_val * 100:.4f}%")
            print(f"-> Cuota Calculada:  S/ {cuota_calc:,.2f}")
            
            diff = abs(cuota_calc - Decimal(str(case['cuota'])))
            if diff < 0.05:
                print("\033[92m-> ¡COINCIDE CON EL ENUNCIADO! (Diferencia menor a S/ 0.05)\033[0m")
            else:
                print(f"\033[93m-> Diferencia de S/ {diff:.2f} con el enunciado.\033[0m")
                
            print("-" * 50)
            
            # Conexión a BD y búsqueda
            with engine.connect() as conn:
                db_client = buscar_cliente_bd(conn, case["cliente"])
                if not db_client:
                    print(f"\033[91mError: No se encontró al cliente '{case['cliente']}' en la base de datos dcliente.\033[0m")
                    input("\nPresione Enter para volver...")
                    continue
                    
                print(f"Cliente ubicado en BD:")
                print(f"-> ID Cliente (pkcliente): {db_client['pkcliente']}")
                print(f"-> Código (codcliente):    {db_client['codcliente'].strip()}")
                print(f"-> Nombre completo en BD:  {db_client['nomcliente'].strip()}")
                print("-" * 50)
                
                # Paso 1: Solicitar
                resp = input("¿Desea REGISTRAR esta solicitud de crédito en la base de datos? (s/n): ").strip().lower()
                if resp != 's':
                    continue
                    
                # Convertir fecha desembolso a YYYY-MM-DD
                fecha_des_dt = datetime.strptime(case["desembolso"], "%d-%m-%Y")
                fecha_des_str = fecha_des_dt.strftime("%Y-%m-%d")
                
                try:
                    sol_res = repo_creditos.crear_solicitud(
                        conn,
                        pkcliente=db_client["pkcliente"],
                        montosolicitud=monto_val,
                        plazo=plazo_val,
                        codtipocredito="ME", # Microempresa
                        codactividadeconomica="4711", # CIIU bodega
                        montoingresoneto=monto_val * 2, # ingreso seguro
                        con_seguro=case["con_seguro"],
                        fecha_desembolso=fecha_des_str,
                        dia_pago=case["dia_pago"]
                    )
                    pksolicitud = sol_res["pksolicitud"]
                    codsolicitud = sol_res["codsolicitud"]
                    print(f"\033[92m✔ ¡Solicitud registrada exitosamente!\033[0m")
                    print(f"-> ID Solicitud:  {pksolicitud}")
                    print(f"-> Cód Solicitud: {codsolicitud}")
                    print("-" * 50)
                except Exception as ex:
                    print(f"\033[91mError al registrar la solicitud: {ex}\033[0m")
                    conn.rollback()
                    input("\nPresione Enter para continuar...")
                    continue
                
                # Paso 2: Evaluar
                resp = input("¿Desea EVALUAR la solicitud para aprobarla y ver el cronograma? (s/n): ").strip().lower()
                if resp != 's':
                    continue
                    
                try:
                    eval_res = repo_creditos.evaluar_solicitud(conn, pksolicitud)
                    cronograma = eval_res["cronograma"]
                    print(f"\033[92m✔ ¡Solicitud aprobada y evaluada!\033[0m")
                    print(f"Cronograma generado (Primeras 2 y última cuotas):")
                    print("-" * 75)
                    print(f"{'N°':<4} | {'Fecha Pago':<12} | {'Cuota':<10} | {'Capital':<10} | {'Interés':<10} | {'Saldo Cap':<10}")
                    print("-" * 75)
                    
                    # Mostrar las primeras 2
                    for c in cronograma[:2]:
                        print(f"{c['nrocuota']:<4} | {c['fecha_vencimiento']:<12} | S/ {c['monto_cuota']:<7.2f} | S/ {c['capital']:<7.2f} | S/ {c['interes']:<7.2f} | S/ {c['saldo_capital']:<7.2f}")
                    
                    if len(cronograma) > 3:
                        print("...")
                    
                    # Mostrar la última
                    if len(cronograma) >= 3:
                        c = cronograma[-1]
                        print(f"{c['nrocuota']:<4} | {c['fecha_vencimiento']:<12} | S/ {c['monto_cuota']:<7.2f} | S/ {c['capital']:<7.2f} | S/ {c['interes']:<7.2f} | S/ {c['saldo_capital']:<7.2f}")
                    print("-" * 75)
                    print(f"Suma total de cuotas: S/ {eval_res['monto_total']:,.2f}")
                    print("-" * 50)
                except Exception as ex:
                    print(f"\033[91mError al evaluar la solicitud: {ex}\033[0m")
                    conn.rollback()
                    input("\nPresione Enter para continuar...")
                    continue
                    
                # Paso 3: Desembolsar
                resp = input("¿Desea DESEMBOLSAR el crédito y abonarlo al ahorro del cliente? (s/n): ").strip().lower()
                if resp != 's':
                    continue
                    
                try:
                    des_res = repo_creditos.desembolsar_solicitud(conn, pksolicitud)
                    print(f"\033[92m✔ ¡Crédito desembolsado exitosamente!\033[0m")
                    print(f"-> ID Cuenta Crédito: {des_res['pkcuentacredito']}")
                    print("-> El monto ha sido abonado a la cuenta de ahorros del cliente.")
                    print("-> Se registraron los asientos correspondientes en foperaciones.")
                    print("-" * 50)
                except Exception as ex:
                    print(f"\033[91mError al desembolsar: {ex}\033[0m")
                    conn.rollback()
                    
            input("\nFlujo del caso completado. Presione Enter para volver al menú...")
            
        elif opc == "3":
            print("\n¡Gracias por practicar!")
            break
        else:
            print("Opción inválida.")
            input("\nPresione Enter para continuar...")

if __name__ == "__main__":
    main()
