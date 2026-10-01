"""Pruebas automáticas del dashboard (sin abrir el navegador).
Uso:  python tests/test_app.py
"""
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def nueva():
    return AppTest.from_file(APP, default_timeout=60).run()


def ms(at, etiqueta):
    return next(w for w in at.sidebar.multiselect if w.label == etiqueta)


def textos(at):
    return " ".join(str(e.value) for e in list(at.warning) + list(at.info) + list(at.markdown))


def main():
    # 1. Sin filtros: sin errores, 4 indicadores, 5 pestañas, 3 decisiones activadas
    at = nueva()
    assert not at.exception, at.exception
    assert [m.label for m in at.metric] == ["Tickets", "Cumplimiento de SLA", "Reincidencia a 30 días",
                                            "Mediana de resolución"]
    assert at.metric[0].value == "4.836" and len(at.tabs) == 5
    assert textos(at).count("🔴 Activar") == 3
    print("1 OK  sin filtros:", [m.value for m in at.metric], "· 3 decisiones activadas")

    # 2. Filtro por zona rural cambia los indicadores
    at = nueva(); ms(at, "Zona").select("Rural").run()
    assert not at.exception and at.metric[0].value != "4.836"
    print("2 OK  zona Rural:", at.metric[0].value, "tickets · SLA", at.metric[1].value)

    # 3. El semáforo reacciona: solo fibra -> D1 queda en rango
    at = nueva(); ms(at, "Tecnología").select("FTTH").run()
    assert not at.exception and textos(at).count("🟢 En rango") >= 1
    print("3 OK  solo FTTH: D1 pasa a 'En rango'")

    # 4. Grupo pequeño -> advertencia visible
    at = nueva(); ms(at, "Nodo").select("N-MEJ-01").run(); ms(at, "Tipo de falla").select("Equipo dañado").run()
    assert not at.exception and "menos de 30" in textos(at)
    print("4 OK  grupo pequeño:", at.metric[0].value, "tickets -> advertencia mostrada")

    # 5. Filtros sin resultados -> mensaje y sin errores
    at = nueva(); ms(at, "Tecnología").select("FTTH").run(); ms(at, "Nodo").select("N-CAY-02").run()
    assert not at.exception and "Ningún ticket" in textos(at)
    print("5 OK  sin resultados: mensaje mostrado")

    # 6. Rango de fechas corto (una semana)
    at = nueva(); at.sidebar.date_input[0].set_value((date(2026, 3, 2), date(2026, 3, 8))).run()
    assert not at.exception
    print("6 OK  semana 2-8 mar:", at.metric[0].value, "tickets")

    # 7. Tabla de detalle por nodo
    at = nueva(); at.selectbox[0].set_value("Nodo").run()
    assert not at.exception and len(at.dataframe) == 1
    print("7 OK  detalle por nodo")
    print("\nTodas las pruebas del dashboard pasaron.")


if __name__ == "__main__":
    main()
