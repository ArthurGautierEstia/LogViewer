import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
import plotly.express as px
import plotly.io as pio
from tkinterhtml import HtmlFrame  # Assurez-vous d'installer tkinterhtml
import webbrowser
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import Counter
import numpy as np
import json

class KukaRsiLogViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analyseur de Log KUKA RSI")
        self.geometry("800x600")
        self.selectedLogFile = ""

        self.data = defaultdict(list)

        # Frame pour les contrôles
        controls_frame = tk.Frame(self)
        controls_frame.pack(pady=10, padx=10, fill=tk.X)

        self.load_button = tk.Button(controls_frame, text="Charger un fichier de log", command=self.load_file)
        self.load_button.pack(side=tk.LEFT, padx=(0, 10))

        self.tag_label = tk.Label(controls_frame, text="Tag à afficher :")
        self.tag_label.pack(side=tk.LEFT)

        self.tag_selector = ttk.Combobox(controls_frame, state="readonly", width=40)
        self.tag_selector.pack(side=tk.LEFT, expand=True, fill=tk.X)
        #self.tag_selector.bind("<<ComboboxSelected>>", self.export_to_html_interactif)

        # Frame pour afficher le graphique Plotly
        self.html_frame = HtmlFrame(self)
        self.html_frame.pack(fill=tk.BOTH, expand=True)

    def load_file(self):
        filepath = filedialog.askopenfilename(
            title="Ouvrir un fichier de log",
            filetypes=(("Log Files", "*.log"), ("All files", "*.*"))
        )
        if not filepath:
            messagebox.showwarning("Problème d'importation", "Fichier introuvable")
            return
        
        # Nom du fichier sans extension
        self.selectedLogFile = os.path.splitext(os.path.basename(filepath))[0]
        
        self.parse_log_file(filepath)

    def parse_log_file(self, filepath):
        self.data.clear()
        xml_pattern = re.compile(r'(<.*>.*)')

        with open(filepath, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                match = xml_pattern.search(line)
                if match:
                    xml_string = match.group(1).replace('\\"', '"').replace('\\n', '')
                    #print(f"Ligne {line_number}: Trame XML trouvée: {xml_string}")
                    try:
                        root = ET.fromstring(xml_string)
                        self._extract_paths_from_element(root)
                    except ET.ParseError as e:
                        #print(f"Ligne {line_number}: Erreur de parsing XML: {e}")
                        continue

        if not self.data:
            messagebox.showwarning("Aucune donnée", "Aucune trame XML valide n'a été trouvée dans ce fichier.")
            return

        self.tag_selector['values'] = sorted(self.data.keys())
        self.tag_selector.set("Sélectionnez un tag")

        html_file_path = "interactive_log_" + self.selectedLogFile + ".html"

        res = messagebox.askyesno(
            "Succès",
            f"{len(self.data)} tags de données trouvés et chargés.\n\nVoulez-vous exporter vers le HTML interactif ({html_file_path}) ?"
        )
        if res:
            self.export_to_html_interactif(html_file_path)
            messagebox.showinfo("Export interactif", f"Le fichier {html_file_path}.html a été généré.")
            webbrowser.open(os.path.abspath(html_file_path))

    def _extract_paths_from_element(self, element, path=''):
        current_path = f"{path}/{element.tag}" if path else element.tag
        if element.text and element.text.strip():
            try:
                value = float(element.text.strip())
                self.data[current_path].append(value)
            except (ValueError, TypeError):
                pass

        for attr, attr_value in element.attrib.items():
            attr_path = f"{current_path}@{attr}"
            try:
                value = float(attr_value)
                self.data[attr_path].append(value)
            except (ValueError, TypeError):
                pass

        for child in element:
            self._extract_paths_from_element(child, current_path)

    def plot_selected_tag(self, event=None):
        selected_tag = self.tag_selector.get()
        if not selected_tag or selected_tag not in self.data:
            return

        values = self.data[selected_tag]

        print(f"Génération des graphiques pour le tag '{selected_tag}'...")
        print(f"Nombre de valeurs trouvées : {len(values)}")
        if not values:
            messagebox.showwarning("Données vides", f"Le tag '{selected_tag}' ne contient aucune donnée à afficher.")
            return

        is_delay = "delay" in selected_tag.lower()  # mettez ici la condition exacte sur le nom du tag Delay

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(
                f"Graphique en ligne pour {selected_tag}",
                f"Histogramme pour {selected_tag}"
            )
        )

        # Tracé commun : ligne à gauche
        fig.add_trace(
            go.Scatter(
                x=list(range(len(values))), y=values, mode='lines+markers'
            ),
            row=1, col=1
        )

        if is_delay:
            # --- Votre configuration spéciale Delay conservée ---
            fig.add_trace(
                go.Histogram(
                    x=values,
                    autobinx=False,
                    xbins=dict(
                        start=min(values) - 0.5,
                        end=max(values) + 0.5,
                        size=1
                    ),
                    marker=dict(
                        line=dict(width=1, color="white"),
                        color="#1f77b4"
                    )
                ),
                row=1, col=2
            )
            fig.update_yaxes(range=[0, 20], title_text="Nombre d'occurrences", row=1, col=2)
            fig.update_layout(
                height=800,
                title_text=f"Analyse complète pour : {selected_tag}",
                showlegend=False,
                margin=dict(t=120)
            )
            mean_delay = np.mean(values)
            percent_nonzero = 100 * sum(1 for v in values if v != 0) / len(values)
            # Texte du cadre (formatté sur 2 lignes)
            info_text = (
                f"<b>Statistiques</b><br>"
                f"Moyenne : {mean_delay:.2f}<br>"
                f"Retards : {percent_nonzero:.1f}%"
            )
            fig.add_annotation(
                text=info_text,
                xref="paper", yref="paper",
                x=0.99, y=0.99,                   # Coin supérieur droit
                showarrow=False,
                align="left",
                font=dict(size=14, color="white"),
                bordercolor="white",
                borderwidth=1,
                borderpad=8,
                bgcolor="#1f77b4",                 # Teinte de fond adaptée
                opacity=0.85
            )

            counts = Counter(values)
            for x_val, y_val in counts.items():
                if y_val >=1000:
                    fig.add_annotation(
                        x=x_val, y=18.8, text=str(y_val), showarrow=False,
                        yanchor="bottom", xref="x2", yref="y2",
                        textangle=90, font=dict(color="white")
                    )
                elif y_val <1000 and y_val >=100:
                    fig.add_annotation(
                        x=x_val, y=19.1, text=str(y_val), showarrow=False,
                        yanchor="bottom", xref="x2", yref="y2",
                        textangle=90, font=dict(color="white")
                    )
                elif y_val <100 and y_val >=20 :
                    fig.add_annotation(
                        x=x_val, y=19.3, text=str(y_val), showarrow=False,
                        yanchor="bottom", xref="x2", yref="y2",
                        textangle=90, font=dict(color="white")
                    )
                elif y_val <20 and y_val >=10:
                    fig.add_annotation(
                        x=x_val, y=y_val-0.7, text=str(y_val), showarrow=False,
                        yanchor="bottom", xref="x2", yref="y2",
                        textangle=90, font=dict(color="white")
                    )
                else:
                    fig.add_annotation(
                        x=x_val, y=y_val-0.5, text=str(y_val), showarrow=False,
                        yanchor="bottom", xref="x2", yref="y2",
                        textangle=0, font=dict(color="white")
                    )

        else:
            # --- Affichage standard & auto-adaptatif pour tous les autres tags ---
            fig.add_trace(
                go.Histogram(
                    x=values,
                    marker=dict(
                        line=dict(width=1, color="white"),
                        color="#1f77b4"
                    )
                ),
                row=1, col=2
            )
            fig.update_yaxes(title_text="Nombre d'occurrences", row=1, col=2)
            fig.update_layout(
                height=800,
                title_text=f"Analyse pour : {selected_tag}",
                showlegend=False,
                margin=dict(t=80)
            )

        fig.update_xaxes(title_text="Index de la trame", row=1, col=1)
        fig.update_yaxes(title_text=f"{selected_tag}", row=1, col=1)
        fig.update_xaxes(title_text=selected_tag, row=1, col=2)

        html_file_path = "graphiques_combines.html"
        fig.write_html(html_file_path)
        messagebox.showinfo("Succès", f"Graphiques sauvegardés dans {html_file_path}")
        webbrowser.open(f"file://{os.path.abspath(html_file_path)}")

    def export_to_html_interactif(self, output_path="kuka_log_interactif.html"):
        all_data = {tag: values for tag, values in self.data.items() if values}
        all_data_json = json.dumps(all_data)

        html_template = f'''<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>KUKA Log Viewer Interactif</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            html, body {{
                height: 100vh; margin: 0; padding: 0; background: #181c21; color: #fff;
                font-family: Arial,sans-serif;
            }}
            #main-container {{
                display: flex; flex-direction: row; height: 100vh; width: 100vw;
            }}
            #sidebar {{
                background:#20242b;
                min-width:235px; max-width:335px;
                padding:22px 14px 12px 14px;
                overflow-y:auto; height:100vh;
                border-right: 1px solid #282a30;
            }}
            #plot-container {{
                flex:1;
                padding: 26px 34px 30px 36px;
                overflow:auto;
                height:100vh;
                background: #181c21;
            }}
            #plot-container > div {{
                margin-bottom: 60px;
                width: 100%;
                min-height: 540px;
            }}
            .plot-header {{
                font-family:sans-serif;font-weight:bold;margin-bottom:5px;
            }}
            .stats-box {{
                color:white;background-color:#1f77b4;
                border:1px solid #fff;border-radius:5px;padding:10px 15px;
                display:inline-block;opacity:0.92;margin-bottom:8px;font-size:15px;
            }}
            #checkbox-list {{ columns:1 auto; }}
            button {{ margin-top:11px;margin-bottom:6px;padding:4px 9px; }}
            label {{ font-size: 15px; }}
            @media (max-width: 900px) {{
                #main-container {{ flex-direction: column; }}
                #sidebar {{ max-width: 100vw; min-width:110px; border-right:none; border-bottom:1px solid #282a30; height:auto; }}
                #plot-container {{ height: auto; padding: 8px 4px 16px 6px; }}
            }}
        </style>
    </head>
    <body>
        <div id="main-container">
            <div id="sidebar">
                <label style="font-size:16px;"><input type="checkbox" id="same-plot"> Tout sur le même graphe</label>
                <br/><br/>
                <strong>Tags à afficher&nbsp;:</strong>
                <div id="checkbox-list"></div>
                <button id="plot-btn">Tracer</button>
                <button id="select-all" style="margin-left:8px;">Tout sélectionner</button>
                <button id="select-none" style="margin-left:4px;">Aucun</button>
                <br>
            </div>
            <div id="plot-container"></div>
        </div>
        <script>
        // Données exportées (injectées)
        const all_data = {all_data_json};

        // Initialiser la liste de checkboxes
        const checkboxList = document.getElementById('checkbox-list');
        const tags = Object.keys(all_data);
        function renderCheckboxes() {{
            checkboxList.innerHTML = '';
            tags.forEach(tag => {{
                let cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.id = 'cb-'+btoa(tag);
                cb.value = tag;
                cb.checked = false;
                checkboxList.appendChild(cb);
                let label = document.createElement('label');
                label.innerHTML = '&nbsp;' + tag;
                label.htmlFor = cb.id;
                checkboxList.appendChild(label);
                checkboxList.appendChild(document.createElement('br'));
            }});
        }}
        renderCheckboxes();

        // Select all / none
        document.getElementById("select-all").onclick = function() {{
            document.querySelectorAll('#checkbox-list input[type=checkbox]').forEach(cb => cb.checked = true);
        }};
        document.getElementById("select-none").onclick = function() {{
            document.querySelectorAll('#checkbox-list input[type=checkbox]').forEach(cb => cb.checked = false);
        }};

        // Tracé des graphes
        function plotGraphs() {{
            const selectedTags = Array.from(document.querySelectorAll('#checkbox-list input:checked')).map(cb => cb.value);
            const samePlot = document.getElementById('same-plot').checked;
            const container = document.getElementById('plot-container');
            container.innerHTML = '';

            if (selectedTags.length === 0) {{
                container.innerHTML = "<p>Aucun tag sélectionné.</p>";
                return;
            }}

            if (samePlot) {{
                let traces = [];
                selectedTags.forEach(tag => {{
                    let values = all_data[tag];
                    traces.push({{
                        x: Array.from({{length: values.length}}, (_, i) => i),
                        y: values,
                        type: 'scatter',
                        mode: 'lines+markers',
                        name: tag,
                        yaxis: 'y'
                    }});
                }});
                let layout = {{
                    paper_bgcolor: "#181c21", plot_bgcolor: "#20242b",
                    title: 'Tags superposés',
                    xaxis: {{title: 'Index de la trame', color:'#fff'}},
                    yaxis: {{title: 'Valeur', color:'#fff'}},
                    legend: {{font:{{color:'white'}}}},
                    margin: {{t: 60, l: 65, r:32, b: 50}},
                    autosize:true
                }};
                let div = document.createElement('div');
                div.style.width = "100%"; div.style.minHeight = "580px";
                container.appendChild(div);
                Plotly.newPlot(div, traces, layout, {{responsive:true, displaylogo:false}});
            }} else {{
                selectedTags.forEach(tag => {{
                    let values = all_data[tag];
                    let isDelay = tag.toLowerCase().includes("delay");
                    let div = document.createElement('div');
                    div.style.width = "100%"; div.style.minHeight = "540px";
                    container.appendChild(div);

                    // ---------- SPECIAL DELAY ----------
                    if (isDelay && values.length > 0) {{
                        let mean = values.reduce((a,b) => a+b, 0)/values.length;
                        let percent_nonzero = 100*values.filter(v => v !== 0).length/values.length;
                        let stats_html = `<span class="stats-box">
                            <b>Statistiques</b><br/>
                            Moyenne : ${{mean.toFixed(2)}}<br/>
                            Retards ≠0 : ${{percent_nonzero.toFixed(1)}}%
                        </span>`;
                        let supTitle = `<div class="plot-header"><span style="color:#97eafc;">${{tag}}</span></div>`;
                        // Ajoute le texte d'infos/statistiques
                        div.innerHTML = supTitle + stats_html;
                        // Crée un sous-div pour Plotly
                        let plotdiv = document.createElement('div');
                        plotdiv.style.width = "100%";
                        plotdiv.style.minHeight = "540px";
                        div.appendChild(plotdiv);

                        // Histogramme Delay (avec annotations verticales)
                        let counts = values.reduce((acc, v) => (acc[v]=1+(acc[v]||0), acc), {{}});
                        let xVals = Object.keys(counts).map(Number).sort((a,b)=>a-b);
                        let yVals = xVals.map(x=>counts[x]);
                        // Data
                        let figData = [
                            {{
                                x: Array.from({{length: values.length}}, (_, i) => i),
                                y: values, type:"scatter", mode:"lines+markers",
                                marker:{{color:"#63b2ea"}},
                                name:"Série temporelle"
                            }},
                            {{
                                x: xVals,
                                y: yVals,
                                type:"bar",
                                marker:{{
                                    line:{{width:1,color:"#fff"}},
                                    color:"#1f77b4"
                                }},
                                name:"Histogramme",
                                xaxis:"x2",
                                yaxis:"y2",
                                showlegend:false
                            }}
                        ];
                        let annots = yVals.map((yv, i) => {{
                            let angle = (yv>=10)? 90 : 0;
                            let y_text = ((yv>=1000)? 18.6 : (yv >=100 ? 18.9 :(yv>=20?19.1: yv-(yv>=10?0.9:0.7))));
                            return {{
                                x: xVals[i], y: y_text,
                                yanchor:"bottom", text: yv.toString(), showarrow:false,
                                xref:"x2", yref:"y2", textangle:angle,
                                font:{{color:"white",size:10}}
                            }};
                        }});

                        let figLayout = {{
                            paper_bgcolor: "#181c21", plot_bgcolor: "#20242b",
                            title: `Analyse complète pour :  ${{tag}}`,
                            grid:{{rows:1, columns:2, pattern:"independent"}},
                            xaxis: {{domain:[0.0,0.47],title:"Index de la trame",color:'#fff', automargin:true}},
                            yaxis: {{domain:[0,1],title:tag,color:'#fff', automargin:true}},
                            xaxis2: {{domain:[0.53,1.0],title:tag,color:'#fff', automargin:true}},
                            yaxis2: {{domain:[0,1],title:"Nombre d'occurrences",color:'#fff',range:[0,20], automargin:true}},
                            annotations: annots,
                            showlegend:false,
                            margin:{{t:90, b:46, l:66, r:38}},
                            autosize:true
                        }};
                        Plotly.newPlot(plotdiv, figData, figLayout, {{responsive:true, displaylogo:false}});
                    }} else if (values.length > 0) {{
                    // ---------- STANDARD / NON-DELAY ----------
                        let supTitle = `<div class="plot-header">Tag&nbsp;<span style="color:#97eafc;"> ${{tag}}</span></div>`;
                        div.innerHTML = supTitle;
                        let figData = [
                            {{
                                x: Array.from({{length: values.length}}, (_, i) => i),
                                y: values,
                                type:"scatter", mode:"lines+markers",
                                marker:{{color:"#63b2ea"}},
                                name:"Série temporelle"
                            }},
                            {{
                                x: values,
                                type:"histogram",
                                marker:{{line:{{width:1, color:"#fff"}},color:"#1f77b4"}},
                                name:"Histogramme",
                                xaxis:"x2", yaxis:"y2"
                            }}
                        ];
                        let figLayout = {{
                            paper_bgcolor: "#181c21", plot_bgcolor: "#20242b",
                            title: `Analyse pour :  ${{tag}}`,
                            grid:{{rows:1, columns:2, pattern:"independent"}},
                            xaxis: {{domain:[0.0,0.47],title:"Index de la trame", color:'#fff', automargin:true}},
                            yaxis: {{domain:[0,1],title:tag, color:'#fff', automargin:true}},
                            xaxis2: {{domain:[0.53,1.0],title:tag, color:'#fff', automargin:true}},
                            yaxis2: {{domain:[0,1],title:"Nombre d'occurrences", color:'#fff', automargin:true}},
                            showlegend:false,
                            margin:{{t:70, b:45, l:58, r:36}},
                            autosize:true
                        }};
                        Plotly.newPlot(div, figData, figLayout, {{responsive:true, displaylogo:false}});
                    }}
                }});
            }}
        }}

        document.getElementById('plot-btn').onclick = plotGraphs;

        // Option : rendre le plot auto au chargement si tu veux
        // window.onload = () => plotGraphs();
        </script>
    </body>
    </html>
    '''

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"Fichier HTML interactif généré : {output_path}")


if __name__ == "__main__":
    app = KukaRsiLogViewer()
    app.mainloop()
