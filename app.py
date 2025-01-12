import sqlite3
from flask import Flask, render_template, render_template_string, request, Response, url_for
import folium
from folium.plugins import MarkerCluster
import requests
import re
import time
import logging
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # Wymusza użycie backendu bez GUI
import matplotlib.pyplot as plt
import io


# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)

# Functions for database connection
def polaczZBaza():
    return sqlite3.connect('logs_database.db')








# Funkcja do pobierania danych z bazy (Ranking IP)
def get_top_ips(table):
    query = f"""
        SELECT ip, COUNT(*) as request_count
        FROM {table}
        GROUP BY ip
        ORDER BY request_count DESC
        LIMIT 4;
    """
    try:
        conn = polaczZBaza()
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        return results  # Zwraca listę [(ip, liczba_zapytań), ...]
    except sqlite3.Error as e:
        print(f"Błąd bazy danych: {e}")
        return []

# Funkcja do pobierania danych z bazy (Metody HTTP)
def get_http_methods(table):
    query = f"""
        SELECT method, COUNT(*) as method_count
        FROM {table}
        GROUP BY method;
    """
    try:
        conn = polaczZBaza()
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        return results  # Zwraca listę [(method, liczba_wystąpień), ...]
    except sqlite3.Error as e:
        print(f"Błąd bazy danych: {e}")
        return []

# Funkcja do pobierania danych z bazy (Próby nieautoryzowanego dostępu - statusy HTTP)
def get_http_status_codes(table):
    query = f"""
        SELECT status, COUNT(*) as count
        FROM {table}
        WHERE (status BETWEEN 200 AND 299) OR (status BETWEEN 300 AND 399) 
              OR (status BETWEEN 400 AND 499) OR (status BETWEEN 500 AND 599)
        GROUP BY status;
    """
    try:
        conn = polaczZBaza()
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        # Grupowanie statusów w odpowiednich przedziałach
        grouped_status = {
            'Sukces (200-299)': 0,
            'Przekierowanie (300-399)': 0,
            'Błąd klienta (400-499)': 0,
            'Błąd serwera (500-599)': 0,
        }

        # Sumowanie wystąpień kodów statusu w grupach
        for row in results:
            status_code = row[0]
            count = row[1]
            if 200 <= status_code <= 299:
                grouped_status['Sukces (200-299)'] += count
            elif 300 <= status_code <= 399:
                grouped_status['Przekierowanie (300-399)'] += count
            elif 400 <= status_code <= 499:
                grouped_status['Błąd klienta (400-499)'] += count
            elif 500 <= status_code <= 599:
                grouped_status['Błąd serwera (500-599)'] += count

        return grouped_status
    except sqlite3.Error as e:
        print(f"Błąd bazy danych: {e}")
        return {}

# Endpoint do generowania wykresu słupkowego (Ranking IP)
@app.route('/top_ips_chart/<table>')
def top_ips_chart(table):
    data = get_top_ips(table)
    fig, ax = plt.subplots(figsize=(6, 4.3))

    if data:
        ips = [item[0] for item in data]
        request_counts = [item[1] for item in data]

        colors = plt.cm.Reds([0.8 - 0.2 * i for i in range(len(ips))])

        bars = ax.bar(ips, request_counts, color=colors, edgecolor='black', width=0.35)
        ax.set_xlabel('Adres IP', fontsize=12)
        ax.set_ylabel('Liczba zapytań', fontsize=12)
        ax.grid(axis='y', linestyle='--', alpha=0.7)

        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height, f'{height}', ha='center', va='bottom', fontsize=10)
    else:
        ax.text(0.5, 0.5, 'Brak danych', ha='center', va='center', fontsize=12)
        ax.axis('off')

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return Response(img, mimetype='image/png')

@app.route('/http_methods_chart/<table>')
def http_methods_chart(table):
    data = get_http_methods(table)
    fig, ax = plt.subplots(figsize=(8, 6))

    if data:
        methods = [item[0] for item in data]
        counts = [item[1] for item in data]

        colors = plt.cm.Paired(range(len(methods)))

        wedges, texts, autotexts = ax.pie(
            counts,
            colors=colors,
            autopct='%1.1f%%',
            startangle=140,
            textprops={'fontsize': 10},
            wedgeprops={'linewidth': 1, 'edgecolor': 'black', 'width': 0.66}
        )

        total = sum(counts)

        ax.text(0, 0.1, 'Total', ha='center', va='center', fontsize=10, fontweight='normal')
        ax.text(0, -0.1, f'{total}', ha='center', va='center', fontsize=12, fontweight='bold')

        legend = fig.legend(
            wedges,
            methods,
            title="Metody HTTP",
            loc="lower center",
            bbox_to_anchor=(0.5, 0.1),
            ncol=len(methods),
            frameon=False,
            fontsize=10
        )

        line = plt.Line2D([0.1, 0.9], [0.22, 0.22], color='black', lw=0.8, transform=fig.transFigure, clip_on=False)
        fig.add_artist(line)

        fig.subplots_adjust(bottom=0.25)
    else:
        ax.text(0.5, 0.5, 'Brak danych', ha='center', va='center', fontsize=12)
        ax.axis('off')

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return Response(img, mimetype='image/png')

@app.route('/http_status_pie_chart/<table>')
def http_status_pie_chart(table):
    data = get_http_status_codes(table)
    fig, ax = plt.subplots(figsize=(4, 3))

    if data:
        labels = list(data.keys())
        sizes = list(data.values())

        colors = plt.cm.Paired(range(len(labels)))

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=None,
            autopct='%1.1f%%',
            startangle=140,
            colors=colors,
            textprops={'fontsize': 10},
            wedgeprops={'linewidth': 1, 'edgecolor': 'black'}
        )

        ax.legend(
            wedges, labels,
            title="Kategorie",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            fontsize=9
        )

        ax.axis('equal')
    else:
        ax.text(0.5, 0.5, 'Brak danych', ha='center', va='center', fontsize=12)
        ax.axis('off')

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    return Response(img, mimetype='image/png')



















def pobierzAdresyZTabel(tabele):
    zapytanie = " UNION ".join([f"SELECT ip FROM {tabela}" for tabela in tabele])
    with polaczZBaza() as baza:
        kursor = baza.cursor()
        return [wiersz[0] for wiersz in kursor.execute(f"SELECT DISTINCT ip FROM ({zapytanie})").fetchall()]

def pobierzWszystkoZTabeli(tabela):
    zapytanie_schemat = f"PRAGMA table_info({tabela})"
    zapytanie_dane = f"SELECT * FROM {tabela}"
    with polaczZBaza() as baza:
        kursor = baza.cursor()
        nazwy_kolumn = [kolumna[1] for kolumna in kursor.execute(zapytanie_schemat)]
        dane_tabeli = kursor.execute(zapytanie_dane).fetchall()
        return nazwy_kolumn, dane_tabeli

def pobierzPrzetlumaczoneAdresy():
    with polaczZBaza() as baza:
        kursor = baza.cursor()
        return [wiersz[0] for wiersz in kursor.execute("SELECT ip FROM translated_addresses").fetchall()]

def pobierzAdresWykSzer():
    with polaczZBaza() as baza:
        kursor = baza.cursor()
        return [
            {"ip": wiersz[0], "lat": wiersz[1], "lon": wiersz[2]}
            for wiersz in kursor.execute("SELECT ip, lat, lon FROM translated_addresses WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchall()
        ]

def przetlumaczAdresy(adresy):
    wynik = []
    for i in range(0, len(adresy), 100):
        partia = adresy[i:i+100]
        try:
            odpowiedz_api = requests.post("http://ip-api.com/batch", json=partia, timeout=10).json()
        except requests.RequestException as e:
            logging.error(f"Błąd podczas wywołania API: {e}")
            continue
        for wpis in odpowiedz_api:
            if wpis["status"] == "success":
                wynik.append((wpis["query"], wpis["lat"], wpis["lon"]))
            else:
                wynik.append((wpis["query"], None, None))
        time.sleep(1)  # Pauza na potrzeby limitu API
    return wynik

def aktualizujPrzetlumaczoneAdresy(nowe_adresy):
    przetlumaczone_adresy = przetlumaczAdresy(nowe_adresy)
    with polaczZBaza() as baza:
        kursor = baza.cursor()
        kursor.executemany(
            "INSERT INTO translated_addresses (ip, lat, lon) VALUES (?, ?, ?)",
            przetlumaczone_adresy
        )
        baza.commit()

def synchronizujAdresy():
    obecne_adresy = set(pobierzAdresyZTabel(['apache_access_logs', 'nginx_logs']))
    zapisane_adresy = set(pobierzPrzetlumaczoneAdresy())
    nowe_adresy = list(obecne_adresy - zapisane_adresy)
    if nowe_adresy:
        aktualizujPrzetlumaczoneAdresy(nowe_adresy)

# Function for normalizing date format
def normalize_date(log_date):
    pattern = r'(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})'
    months = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
        "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
        "Nov": "11", "Dec": "12"
    }
    match = re.match(pattern, log_date)
    if match:
        day, month_str, year, hour, minute, second = match.groups()
        return f"{year}-{months.get(month_str, '01')}-{day} {hour}:{minute}:{second}"
    return None

# Function to fetch logs and filter by date
def get_filtered_logs(start_date, end_date, tabela):
    if not re.match(r'^[a-zA-Z0-9_]+$', tabela):  # Validate table name
        raise ValueError("Invalid table name.")
    
    query = f"SELECT date_time FROM {tabela}"
    with polaczZBaza() as con:
        cursor = con.cursor()
        rows = cursor.execute(query).fetchall()

    return [
        normalize_date(row[0]) for row in rows
        if normalize_date(row[0]) and start_date <= normalize_date(row[0])[:10] <= end_date
    ]

# Function for date range based on period
def get_date_range(period):
    today = datetime.now()
    if period == "popTydzien":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
    elif period == "aktTydzien":
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == "dzisiaj":
        start = end = today
    else:
        return None, None
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

# Grouping logs by different time intervals
def group_logs(filtered_logs, start_date, end_date, group_by="day"):
    log_counts = {}
    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # End of the day

    if group_by == "day":
        current_date = start_datetime
        while current_date < end_datetime:
            log_counts[current_date.strftime('%Y-%m-%d')] = 0
            current_date += timedelta(days=1)
        for log in filtered_logs:
            date = log[:10]
            if date in log_counts:
                log_counts[date] += 1

    elif group_by == "hour" and len(set(log[:10] for log in filtered_logs)) == 1:
        log_counts = {f"{hour:02d}:00": 0 for hour in range(24)}
        for log in filtered_logs:
            hour = log[11:13] + ":00"
            log_counts[hour] += 1

    elif group_by == "4hour":
        current_datetime = start_datetime
        while current_datetime < end_datetime:
            key = current_datetime.strftime('%Y-%m-%d %H:%M')
            log_counts[key] = 0
            current_datetime += timedelta(hours=4)
        for log in filtered_logs:
            log_time = datetime.strptime(log, '%Y-%m-%d %H:%M:%S')
            for interval_start in log_counts.keys():
                interval_start_dt = datetime.strptime(interval_start, '%Y-%m-%d %H:%M')
                if interval_start_dt <= log_time < interval_start_dt + timedelta(hours=4):
                    log_counts[interval_start] += 1
                    break

    return sorted(log_counts.keys()), [log_counts[key] for key in sorted(log_counts.keys())]

# Flask routes for map and log visualization
@app.route('/')
def index():
    table = request.args.get('table', 'nginx_logs')  # Domyślnie 'nginx_logs'
    codes_count = get_http_status_codes(table)
    return render_template('index.html', codes_count=codes_count, table=table)


@app.route("/tabele")
def tabele():
    nazwyTabel = ["nginx_logs", "apache_error_logs", "apache_access_logs"]
    daneZTabel = [
        {
            "tabela": tabela,
            "kolumny": pobierzWszystkoZTabeli(tabela)[0],
            "dane": pobierzWszystkoZTabeli(tabela)[1],
        }
        for tabela in nazwyTabel
    ]
    return render_template("tabele.html", daneZTabel = daneZTabel)

@app.route("/mapaPoloczen")
def mapaPoloczen():
    adresy = pobierzAdresWykSzer()
    if not adresy:
        print("Brak danych do stworzenia mapy.")
        return
    
    attr = ('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ''contributors, &copy; <a href="https://cartodb.com/attributions">CartoDB</a>')
    mapa = folium.Map(location=[50, 0], tiles="cartodb positron", attr=attr, width="100vw", height="897px", zoom_start=3, min_zoom=3, max_zoom=8, max_bounds=True)
    
    marker_cluster = MarkerCluster(
        name='1000 clustered icons',
        overlay=True,
        control=False,
        icon_create_function=None
    )

    for adres in adresy:
        location = adres["lat"], adres["lon"]
        marker = folium.Marker(location=location)
        popup = f"IP: {adres['ip']}"
        folium.Popup(popup).add_to(marker)
        marker_cluster.add_child(marker)

    marker_cluster.add_to(mapa)

    iframe = mapa.get_root()._repr_html_()

    return render_template_string(
        """
            {% extends "nawigacja.html" %}
            {% block bodyContent %}
                <div style="padding-top: 50px">
                    {{ iframe|safe }}
                </div>
            <script type="text/javascript">
                document.body.style.overflow = "hidden";
            </script>
            {% endblock %}
        """,
        iframe=iframe,
    )

@app.route("/wykresPoloczen/<okresCzasu>")
def wykresPoloczenZakres(okresCzasu):
    tabela = request.args.get("tabela", "nginx_logs")
    start_date, end_date = get_date_range(okresCzasu)
    if not start_date or not end_date:
        return "Nieprawidłowy okres czasu", 400

    filtered_logs = get_filtered_logs(start_date, end_date, tabela)
    delta = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days

    if delta == 0:
        group_by = "hour"  
    elif delta == 1:
        group_by = "4hour"  
    else:
        group_by = "day"  

    dates, counts = group_logs(filtered_logs, start_date, end_date, group_by)

    if delta == 0:
        dates = [date for date in dates]

    okresCzasuWykresu = {
        "popTydzien": f"Wykres z tabeli {tabela}: Poprzedni tydzień (poniedziałek-niedziela)",
        "aktTydzien": f"Wykres z tabeli {tabela}: Bieżący tydzień (poniedziałek-dzisiaj)",
        "dzisiaj": f"Wykres z tabeli {tabela}: Dzisiaj"
    }.get(okresCzasu, "Wykres")

    return render_template('wykresPoloczen.html', dates=dates, counts=counts, okresCzasuWykresu=okresCzasuWykresu)

@app.route("/wykresPoloczen", methods=['GET'])
def search():
    tabela = request.args.get('tabela', 'nginx_logs')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        return "Musisz podać zakres dat", 400

    filtered_logs = get_filtered_logs(start_date, end_date, tabela)
    delta = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days

    if delta == 0:
        group_by = "hour"
    elif delta == 1:
        group_by = "4hour"
    else:
        group_by = "day"

    dates, counts = group_logs(filtered_logs, start_date, end_date, group_by)
    return render_template("wykresPoloczen.html", dates=dates, counts=counts)

if __name__ == "__main__":
    synchronizujAdresy()
    app.run(debug=True)
