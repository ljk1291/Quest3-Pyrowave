"""Lossless registration perturbations in the same output-code metric domain."""
import cv2
import numpy as np


def shift(image, pixels):
    return cv2.warpAffine(image, np.array([[1., 0, pixels], [0, 1., 0]]), image.shape[1::-1],
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def qualified(aggregate):
    limits = [('sat', 'block_rms_p99', .5), ('mura', 'lf8_y_p99', .05)]
    limits += [(name, 'detail_std_p99', .05) for name in aggregate
               if aggregate[name].get('detail_std_p99', {}).get('mean') is not None]
    return all(aggregate.get(name, {}).get(metric, {}).get('mean') is not None and
               aggregate[name][metric]['mean'] <= limit for name, metric, limit in limits)


def annotate(report, controls, diagnostic_controls=None):
    report['registration_controls'] = {step: r['aggregate'] for step, r in controls.items()}
    if diagnostic_controls is not None:
        report['diagnostic_registration_controls'] = {step: r['aggregate'] for step, r in diagnostic_controls.items()}
    report['registration_control_definition'] = ('Lossless forward references with alternating 0/0.25 and 0/0.5 capture-pixel horizontal shifts; '
        'same masks/maps and output code domain. Conservative sensitivity floors, not estimated codec error; '
        '0.25 px controls must meet chroma p99 <=0.5 code, LF8 <=0.05 code and detail std p99 <=0.05 for validation.')
    for key in ('aggregate', 'diagnostic_aggregate'):
        selected_controls = diagnostic_controls if key == 'diagnostic_aggregate' and diagnostic_controls is not None else controls
        for name, metrics in report.get(key, {}).items():
            for metric, row in metrics.items():
                values = [r['aggregate'].get(name, {}).get(metric, {}).get('mean') for r in selected_controls.values()]
                values = [v for v in values if v is not None]
                floor = max(values) if values else None
                row['registration_noise_floor'] = floor
                value = row.get('mean')
                if metric in ('detail_retained_mean', 'detail_correlated_mean'):
                    floor = max((abs(v-1) for v in values), default=None)
                    row['registration_noise_floor'] = floor
                    value = abs(value-1) if value is not None else None
                elif metric.startswith('psnr_'):
                    mse_key = 'mse_'+metric[5:-3]
                    floors = [r['aggregate'].get(name, {}).get(mse_key, {}).get('mean') for r in selected_controls.values()]
                    floor = max((v for v in floors if v is not None), default=None)
                    value = metrics.get(mse_key, {}).get('mean')
                    row['registration_noise_floor'] = floor
                    row['registration_noise_domain'] = mse_key
                row['registration_interpretation'] = ('within registration noise' if value is not None and floor is not None and value <= floor
                                                      else 'above registration control' if value is not None and floor is not None else 'unavailable')
