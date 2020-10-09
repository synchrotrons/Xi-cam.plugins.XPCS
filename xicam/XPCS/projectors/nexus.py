from typing import List
import numpy as np
from databroker.core import BlueskyRun
from xicam.core.data.bluesky_utils import display_name
from xicam.SAXS.intents import SAXSImageIntent
from xicam.core.intents import Intent, PlotIntent, ImageIntent
from ..ingestors import g2_projection_key, g2_error_projection_key, g2_roi_names_key, tau_projection_key, \
                        SAXS_2D_I_projection_key, SAXS_1D_I_projection_key, SAXS_1D_Q_projection_key
from scipy.misc import face


# TODO: Hint -> Intent

# hint -> xicam.intent
# projection -> xicam.intent
# def discover_intents(BlueskyRun) -> List[Intent] # inspects intents and projections to create intents

def project_nxXPCS(run_catalog: BlueskyRun) -> List[Intent]:
    projection = next(
        filter(lambda projection: projection['name'] == 'nxXPCS', run_catalog.metadata['start']['projections']))

    # TODO: project masks, rois
    g2_stream = projection['projection'][g2_projection_key]['stream']
    g2_field = projection['projection'][g2_projection_key]['field']
    tau_field = projection['projection'][tau_projection_key]['field']
    g2_error_field = projection['projection'][g2_error_projection_key]['field']
    g2_roi_name_field = projection['projection'][g2_roi_names_key]['field']
    # Use singly-sourced key name
    g2 = getattr(run_catalog, g2_stream).to_dask().rename({g2_field: g2_projection_key,
                                                        tau_field: tau_projection_key,
                                                        g2_error_field: g2_error_projection_key,
                                                        g2_roi_name_field: g2_roi_names_key})

    SAXS_2D_I_stream = projection['projection'][SAXS_2D_I_projection_key]['stream']
    SAXS_2D_I_field = projection['projection'][SAXS_2D_I_projection_key]['field']
    SAXS_2D_I = getattr(run_catalog, SAXS_2D_I_stream).to_dask().rename({SAXS_2D_I_field: SAXS_2D_I_projection_key})[SAXS_2D_I_projection_key]

    SAXS_1D_I_stream = projection['projection'][SAXS_1D_I_projection_key]['stream']
    SAXS_1D_I_field = projection['projection'][SAXS_1D_I_projection_key]['field']
    SAXS_1D_Q_field = projection['projection'][SAXS_1D_Q_projection_key]['field']
    SAXS_1D_I = getattr(run_catalog, SAXS_1D_I_stream).to_dask().rename({SAXS_1D_I_field: SAXS_1D_I_projection_key,
                                                                         SAXS_1D_Q_field: SAXS_1D_Q_projection_key})
    SAXS_1D_I = np.squeeze(SAXS_1D_I)
    catalog_name = display_name(run_catalog).split(" ")[0]

    l = []
    for i in range(len(g2[g2_projection_key])):
        g2_curve = g2[g2_projection_key][i]
        tau = g2[tau_projection_key][i]
        # g2_roi_name = g2[g2_roi_names_key][i].values[0]
        g2_roi_name = g2[g2_roi_names_key].values[i]  # FIXME: talk to Dan about how to properly define string data keys
        l.append(PlotIntent(item_name=str(g2_roi_name),  # need str cast here, otherwise is type numpy.str_ (which Qt won't like in its DisplayRole)
                            y=g2_curve,
                            x=tau,
                            xLogMode=True,
                            labels={"left": "g2", "bottom": "tau"}))

    #l.append(ImageIntent(image=face(True), item_name='SAXS 2D'),)
    l.append(SAXSImageIntent(image=SAXS_2D_I, item_name="AVG frame {}".format(catalog_name)), )
    l.append(PlotIntent(y=SAXS_1D_I[SAXS_1D_I_projection_key],
                        x=SAXS_1D_I[SAXS_1D_Q_projection_key],
                        labels={"left": "I", "bottom": "Q"},
                        item_name='AVG SAXS curve {}'.format(catalog_name)))
    return l
    # TODO: additionally return intents for masks, rois
