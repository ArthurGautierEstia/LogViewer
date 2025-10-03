import re
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.spatial import cKDTree

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
APT_FILE_PATH = 'apt_source/test.aptsource'
RSI_JSON_PATH = 'jsonOK/kuka_log_cleancdis01v10.json'
ORIGIN_OFFSET = (0, 0, 0)
ORIGIN_ROTATION_DEG = (0, 0, 0)
INTERPOLATION_STEP_MM = 0.01
# --- Seuils de tolérance (ces valeurs ne serviront plus que pour le titre) ---
POSITION_TOLERANCE_MM = 0.5
SPEED_TOLERANCE_MM_S = 5.0

# ==============================================================================
# FONCTIONS 1 à 5 (INCHANGÉES)
# ==============================================================================
def parse_and_transform_apt(filepath, offset_translation, offset_rotation_deg):
    path_segments = []
    rz, ry, rx = offset_rotation_deg
    alpha, beta, gamma = np.radians([rz, ry, rx])
    Rz = np.array([[np.cos(alpha), -np.sin(alpha), 0], [np.sin(alpha), np.cos(alpha), 0], [0, 0, 1]])
    Ry = np.array([[np.cos(beta), 0, np.sin(beta)], [0, 1, 0], [-np.sin(beta), 0, np.cos(beta)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(gamma), -np.sin(gamma)], [0, np.sin(gamma), np.cos(gamma)]])
    rotation_matrix = Rz @ Ry @ Rx
    translation_vector = np.array(offset_translation)
    rapid_speed = 12000.0
    last_point_transformed = None; is_rapid_mode = False; current_feedrate = None
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if "RAPID" in line: is_rapid_mode = True
                elif "FEDRAT" in line:
                    is_rapid_mode = False
                    match = re.search(r'FEDRAT\s*/\s*(-?\d+\.?\d*)', line)
                    if match: current_feedrate = float(match.group(1))
                elif "GOTO" in line:
                    match = re.search(r'GOTO\s*/\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', line)
                    if match:
                        original_point = np.array([float(m) for m in match.groups()])
                        transformed_point = (rotation_matrix @ original_point) + translation_vector
                        if last_point_transformed is not None:
                            path_segments.append({"start": last_point_transformed, "end": transformed_point.tolist(), "feedrate": rapid_speed if is_rapid_mode else current_feedrate})
                        last_point_transformed = transformed_point.tolist()
    except FileNotFoundError: return None
    return path_segments

def densify_theoretical_path(path_segments, step_mm=1.0):
    dense_points = []
    if not path_segments: return pd.DataFrame()
    for segment in path_segments:
        start_point, end_point = np.array(segment['start']), np.array(segment['end'])
        length = np.linalg.norm(end_point - start_point)
        if length == 0: continue
        num_points = int(length / step_mm)
        points = np.linspace(start_point, end_point, num_points, endpoint=False)
        for point in points:
            dense_points.append({'X': point[0], 'Y': point[1], 'Z': point[2], 'Theoretical_Speed_mm_s': segment['feedrate'] / 60.0})
    last_seg = path_segments[-1]
    dense_points.append({'X': last_seg['end'][0], 'Y': last_seg['end'][1], 'Z': last_seg['end'][2], 'Theoretical_Speed_mm_s': last_seg['feedrate'] / 60.0})
    return pd.DataFrame(dense_points)

def load_rsi_data(json_filepath):
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
        timeseries_data = data.get('timeseries')
        positions_data = data.get('tcp_positions')

        # Vérification de l'existence
        if not timeseries_data or not positions_data:
            return None

        # Tronquer tcp_positions si nécessaire pour correspondre à timeseries
        if len(positions_data) != len(timeseries_data):
            min_len = min(len(timeseries_data), len(positions_data))
            timeseries_data = timeseries_data[:min_len]
            positions_data = positions_data[:min_len]

        # Construction du DataFrame
        merged_data = []
        for ts, pos in zip(timeseries_data, positions_data):
            try:
                x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
                speed = float(ts.get('TCP_Speed', 0.0))
                merged_data.append({'Timestamp': ts['Time']/1000.0, 'X': x, 'Y': y, 'Z': z, 'RealSpeed_mm_s': speed})
            except (IndexError, TypeError, ValueError):
                continue  # ignore les points malformés

        if not merged_data:
            return None

        df = pd.DataFrame(merged_data).sort_values(by='Timestamp').reset_index(drop=True)
        return df

    except (FileNotFoundError, Exception):
        return None


def trim_rsi_data(rsi_df, theoretical_start_point):
    if rsi_df is None or theoretical_start_point is None: return None
    real_coords = rsi_df[['X', 'Y', 'Z']].values
    kdtree = cKDTree(real_coords)
    distance, start_index = kdtree.query(theoretical_start_point)
    trimmed_df = rsi_df.iloc[start_index:].copy().reset_index(drop=True)
    print(f"-> Point de départ trouvé (distance: {distance:.3f} mm). {len(rsi_df) - len(trimmed_df)} points d'approche supprimés.")
    return trimmed_df

def synchronize_and_compare(theoretical_df, real_df):
    if theoretical_df.empty or real_df is None or real_df.empty: return None
    real_coords = real_df[['X', 'Y', 'Z']].values
    kdtree = cKDTree(real_coords)
    theoretical_coords = theoretical_df[['X', 'Y', 'Z']].values
    distances, indices = kdtree.query(theoretical_coords)
    results_df = theoretical_df.copy(); results_df.rename(columns={'X': 'X_th', 'Y': 'Y_th', 'Z': 'Z_th'}, inplace=True)
    real_closest_data = real_df.iloc[indices]
    results_df['X_real'], results_df['Y_real'], results_df['Z_real'] = real_closest_data['X'].values, real_closest_data['Y'].values, real_closest_data['Z'].values
    results_df['RealSpeed_mm_s'], results_df['Positional_Error'] = real_closest_data['RealSpeed_mm_s'].values, distances
    results_df['Speed_Error'] = results_df['RealSpeed_mm_s'] - results_df['Theoretical_Speed_mm_s']
    return results_df

def display_summary_statistics(results_df):
    if results_df is None or results_df.empty:
        return

    print("\n" + "="*50 + "\nRÉSUMÉ STATISTIQUE DE LA COMPARAISON\n" + "="*50)

    # --- Erreur de Position ---
    pos_error = results_df['Positional_Error']
    print("\n--- Erreur de Position ---")
    print(f"   Moyenne      : {pos_error.mean():.4f} mm")
    print(f"   Médiane      : {pos_error.median():.4f} mm")
    print(f"   Maximale     : {pos_error.max():.4f} mm")
    print(f"   Minimale     : {pos_error.min():.4f} mm")
    print(f"   Écart-type   : {pos_error.std():.4f} mm")

    # --- Analyse de la Vitesse ---
    speed_error = results_df['Speed_Error']
    print("\n--- Analyse de la Vitesse ---")
    print(f"   Moyenne      : {speed_error.mean():.2f} mm/s")
    print(f"   Médiane      : {speed_error.median():.2f} mm/s")
    print(f"   Maximale     : {speed_error.max():.2f} mm/s")
    print(f"   Minimale     : {speed_error.min():.2f} mm/s")
    print(f"   Écart-type   : {speed_error.std():.2f} mm/s")

    print("="*50 + "\n")


# ==============================================================================
# FONCTION DE VISUALISATION 3D - POSITION (MISE À JOUR)
# ==============================================================================
def visualize_position_comparison(results_df, tolerance_mm):
    """Affiche la comparaison de position 3D avec un dégradé de couleur plus précis."""
    if results_df is None or results_df.empty: return
    fig = go.Figure()

    # Parcours théorique en noir avec opacité réduite par défaut
    fig.add_trace(go.Scatter3d(x=results_df['X_th'], y=results_df['Y_th'], z=results_df['Z_th'], mode='lines', line=dict(color='rgba(0, 0, 0, 0.2)', width=4), name='Parcours Théorique'))

    # Pré-traitement des données pour une meilleure visualisation
    # Utilisation de la racine carrée pour accentuer les petites erreurs
    norm_pos_error = np.sqrt(results_df['Positional_Error'])
    max_norm_pos_error = norm_pos_error.max()
    
    # Parcours réel avec dégradé de couleur (palette jet)
    fig.add_trace(go.Scatter3d(
        x=results_df['X_real'],
        y=results_df['Y_real'],
        z=results_df['Z_real'],
        mode='lines',
        line=dict(
            width=6,
            color=norm_pos_error,
            colorscale='Jet',
            colorbar=dict(title='Erreur de Position (mm)', tickvals=np.linspace(0, max_norm_pos_error, 5), ticktext=[f"{x**2:.2f}" for x in np.linspace(0, max_norm_pos_error, 5)]),
            cmin=-max_norm_pos_error,
            cmax=max_norm_pos_error
        ),
        name='Parcours Réel (Dégradé d\'Erreur)',
    ))

    # Ajout des boutons de contrôle
    updatemenus = [
        dict(
            type="buttons",
            direction="left",
            buttons=list([
                dict(
                    args=[{"line.color": ["rgba(0, 0, 0, 1.0)"]}, [0]],
                    label="Afficher Théorique",
                    method="restyle"
                ),
                dict(
                    args=[{"line.color": ["rgba(0, 0, 0, 0.0)"]}, [0]],
                    label="Masquer Théorique",
                    method="restyle"
                )
            ]),
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.05,
            xanchor="left",
            y=1.05,
            yanchor="top"
        )
    ]

    mean_err, max_err = results_df['Positional_Error'].mean(), results_df['Positional_Error'].max()
    title_text = f'Analyse de Position 3D (Dégradé)<br><sup>Erreur Moyenne: {mean_err:.3f} mm | Erreur Max: {max_err:.3f} mm</sup>'
    fig.update_layout(title=title_text, scene=dict(xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)', aspectmode='data'), legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.6)'), updatemenus=updatemenus)
    fig.show()

# ==============================================================================
# NOUVELLE FONCTION DE VISUALISATION 3D - VITESSE (MISE À JOUR)
# ==============================================================================
def visualize_speed_comparison_3d(results_df, tolerance_mm_s):
    """Affiche la comparaison de vitesse en 3D sur le parcours avec un dégradé plus précis."""
    if results_df is None or results_df.empty: return
    fig = go.Figure()

    # Parcours théorique ombré avec opacité réduite par défaut
    fig.add_trace(go.Scatter3d(x=results_df['X_th'], y=results_df['Y_th'], z=results_df['Z_th'], mode='lines', line=dict(color='rgba(0,0,0,0.1)', width=4), name='Parcours Théorique (Ombre)'))
    
    # Pré-traitement des données pour une meilleure visualisation
    # Centrage de l'échelle à 0 et utilisation d'une transformation racine carrée
    max_abs_speed_err = results_df['Speed_Error'].abs().max()
    norm_speed_error = np.sign(results_df['Speed_Error']) * np.sqrt(np.abs(results_df['Speed_Error']))
    max_norm_speed_err = np.sqrt(max_abs_speed_err)

    # Parcours réel avec dégradé pour l'erreur de vitesse (négatif-positif)
    fig.add_trace(go.Scatter3d(
        x=results_df['X_real'],
        y=results_df['Y_real'],
        z=results_df['Z_real'],
        mode='lines',
        line=dict(
            width=6,
            color=norm_speed_error,
            colorscale='Jet',
            colorbar=dict(
                title='Écart de Vitesse (mm/s)',
                tickvals=np.linspace(-max_norm_speed_err, max_norm_speed_err, 5),
                ticktext=[f"{x*np.abs(x):.2f}" for x in np.linspace(-max_norm_speed_err, max_norm_speed_err, 5)]
            ),
            cmin=-max_norm_speed_err,
            cmax=max_norm_speed_err
        ),
        name='Parcours Réel (Dégradé d\'Écart de Vitesse)',
    ))

    # Ajout des boutons de contrôle
    updatemenus = [
        dict(
            type="buttons",
            direction="left",
            buttons=list([
                dict(
                    args=[{"line.color": ["rgba(0, 0, 0, 1.0)"]}, [0]],
                    label="Afficher Théorique",
                    method="restyle"
                ),
                dict(
                    args=[{"line.color": ["rgba(0, 0, 0, 0.0)"]}, [0]],
                    label="Masquer Théorique",
                    method="restyle"
                )
            ]),
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.05,
            xanchor="left",
            y=1.05,
            yanchor="top"
        )
    ]

    mean_err = abs(results_df['Speed_Error']).mean()
    max_err = abs(results_df['Speed_Error']).max()
    title_text = f'Analyse de Vitesse 3D (Dégradé)<br><sup>Écart Moyen: {mean_err:.2f} mm/s | Écart Max: {max_err:.2f} mm/s</sup>'
    fig.update_layout(title=title_text, scene=dict(xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)', aspectmode='data'), legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.6)'), updatemenus=updatemenus)
    fig.show()

# ==============================================================================
# EXÉCUTION PRINCIPALE
# ==============================================================================
if __name__ == "__main__":
    print("--- DÉBUT DU SCRIPT DE COMPARAISON DE TRAJECTOIRE ---")
    apt_segments = parse_and_transform_apt(APT_FILE_PATH, ORIGIN_OFFSET, ORIGIN_ROTATION_DEG)
    if apt_segments:
        dense_theoretical_df = densify_theoretical_path(apt_segments, step_mm=INTERPOLATION_STEP_MM)
        full_rsi_df = load_rsi_data(RSI_JSON_PATH)
        if full_rsi_df is not None:
            print("\nRecadrage des données RSI au point de départ...")
            theoretical_start_point = dense_theoretical_df[['X', 'Y', 'Z']].iloc[0].values
            trimmed_rsi_df = trim_rsi_data(full_rsi_df, theoretical_start_point)
            print("\nSynchronisation des parcours et calcul des erreurs...")
            comparison_df = synchronize_and_compare(dense_theoretical_df, trimmed_rsi_df)
            
            if comparison_df is not None and not comparison_df.empty:
                display_summary_statistics(comparison_df)
                
                print("Lancement de la visualisation 3D de la POSITION...")
                visualize_position_comparison(comparison_df, POSITION_TOLERANCE_MM)
                
                print("Lancement de la visualisation 3D de la VITESSE...")
                visualize_speed_comparison_3d(comparison_df, SPEED_TOLERANCE_MM_S)
    
    print("\n--- FIN DU SCRIPT ---")