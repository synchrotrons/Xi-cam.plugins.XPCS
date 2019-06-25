from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy import uic
import pyqtgraph as pg

from xicam.core import msg
from xicam.plugins import GUIPlugin, GUILayout, ProcessingPlugin
from xicam.plugins import manager as pluginmanager

from xicam.gui.widgets.tabview import TabView
from xicam.SAXS.widgets.SAXSViewerPlugin import SAXSViewerPluginBase
from xicam.core.data import NonDBHeader
from xicam.gui.widgets.imageviewmixins import PolygonROI
from pyqtgraph.parametertree import ParameterTree, Parameter
from .workflows import OneTime, TwoTime, FourierAutocorrelator

# from . import CorrelationPlugin

# class TwoTimeProcess(ProcessingPlugin):
#     ...
#
#

import numpy as np # TODO -- this is for debugging
# from . import CorrelationDocument


class XPCSViewerPlugin(PolygonROI, SAXSViewerPluginBase):
    pass


class XPCSProcessor(ParameterTree):
    def __init__(self, *args, **kwargs):
        super(XPCSProcessor, self).__init__()

        self.param = Parameter(children=[{'name': 'Algorithm',
                                          'type': 'list',
                                          'values': {OneTime.name: OneTime,
                                                     TwoTime.name: TwoTime,
                                                     FourierAutocorrelator.name: FourierAutocorrelator},
                                          'value': FourierAutocorrelator.name}], name='Processor')
        self.setParameters(self.param, showTop=False)


class CorrelationView(QWidget):
    """
    Widget for viewing the correlation results.

    This could be generalized into a ComboPlotView / PlotView / ComboView ...
    """
    def __init__(self):
        super(CorrelationView, self).__init__()
        self.resultslist = QComboBox()

        self.correlationplot = pg.PlotWidget()

        self.model = self.resultslist.model() # type: QStandardItemModel
        self.selectionmodel = self.resultslist.view().selectionModel()

        layout = QVBoxLayout()
        layout.addWidget(self.resultslist)
        layout.addWidget(self.correlationplot)
        self.setLayout(layout)

        self.selectionmodel.currentChanged.connect(self.updatePlot)

    def updatePlot(self, current, previous):
        self.correlationplot.clear()
        results = self.model.itemFromIndex(current).payload['result']
        # for result in results:
        #     self.correlationplot.plot(
        #         result['g2'].value.squeeze())F
        self.correlationplot.getPlotItem().setLabel('left', 'g<sub>2</sub>(&tau;)')
        self.correlationplot.getPlotItem().setLabel('bottom', '&tau;')
        self.correlationplot.plot(results['g2'].value.squeeze())
        self.resultslist.setCurrentIndex(current.row()) # why doesn't model/view do this for us?

    def appendData(self, data):
        item = QStandardItem(data['name'])
        item.payload = data
        # Do not add if 'name' already in the model TODO temp
        # if self.model.
        self.model.appendRow(item)
        self.selectionmodel.setCurrentIndex(
            self.model.index(self.model.rowCount() - 1, 0), QItemSelectionModel.Rows)
        self.model.dataChanged.emit(QModelIndex(), QModelIndex())

    # def updateViews(self, topleft, bottomright):
    #     self.selectionmodel.currentIndex()



class FileSelectionView(QWidget):
    """
    Widget for viewing and selecting the loaded files.
    """
    def __init__(self, headermodel, selectionmodel):
        """

        Parameters
        ----------
        headermodel
            The model to use in the file list view
        selectionmodel
            The selection model to use in the file list view
        """
        super(FileSelectionView, self).__init__()
        # self.parameters = ParameterTree()
        self.filelistview = QListView()
        self.correlationname = QLineEdit()
        self.correlationname.setPlaceholderText('Name of result')

        layout = QVBoxLayout()
        # layout.addWidget(self.parameters)
        layout.addWidget(self.filelistview)
        layout.addWidget(self.correlationname)
        self.setLayout(layout)

        self.headermodel = headermodel
        self.selectionmodel = selectionmodel
        self.filelistview.setModel(headermodel)
        self.filelistview.setSelectionModel(selectionmodel)
        self.filelistview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.filelistview.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Make sure when the tabview selection model changes, the file list
        # current item updates
        self.selectionmodel.currentChanged.connect(
            lambda current, _: self.filelistview.setCurrentIndex(current)
        )

        self.selectionmodel.currentChanged.connect(
            lambda current, _: self.correlationname.setPlaceholderText(current.data())
        )

    def updateListView(self, start, end):
        pass


class XPCS(GUIPlugin):
    name = 'XPCS'

    def __init__(self):
        # Data model
        self.headermodel = QStandardItemModel()
        self.selectionmodel = QItemSelectionModel(self.headermodel)

        # Widgets
        self.calibrationsettings = pluginmanager.getPluginByName('xicam.SAXS.calibration',
                                                                 'SettingsPlugin').plugin_object

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.addAction('Process', self.process)

        # Setup TabViews
        self.rawtabview = TabView(self.headermodel,
                                  widgetcls=XPCSViewerPlugin,
                                  selectionmodel=self.selectionmodel,
                                  bindings=[(self.calibrationsettings.sigGeometryChanged, 'setGeometry')],
                                  geometry=self.getAI)

        # Setup correlation view
        self.correlationview = CorrelationView()
        self.fileselectionview = FileSelectionView(self.headermodel, self.selectionmodel)
        self.processor = XPCSProcessor()
        self.placeholder = QLabel('correlation parameters')

        self.stages = {'Raw(change)': GUILayout(self.rawtabview,
                                         right=self.calibrationsettings.widget,
                                         top=self.toolbar),
                       'Correlate': GUILayout(self.correlationview,
                                              top=self.toolbar,
                                              right=self.fileselectionview,
                                              rightbottom=self.processor,
                                              bottom=self.placeholder)
                       }

        # TODO -- should CorrelationDocument be a member?
        self.correlationdocument = None

        super(XPCS, self).__init__()

    def appendHeader(self, header: NonDBHeader, **kwargs):
        item = QStandardItem(header.startdoc.get('sample_name', '????'))
        item.header = header
        self.headermodel.appendRow(item)
        self.selectionmodel.setCurrentIndex(self.headermodel.index(self.headermodel.rowCount() - 1, 0),
                                            QItemSelectionModel.Rows)
        self.headermodel.dataChanged.emit(QModelIndex(), QModelIndex())

    def getAI(self):
        return None

    def currentheader(self):
        return self.headermodel.itemFromIndex(self.selectionmodel.currentIndex()).header
        # if self.selectionmodel.selectedIndexes() == 1:
        #     return [self.headermodel.itemFromIndex(self.selectionmodel.currentIndex()).header]
        # else:
        #     model_indices = self.selectionmodel.selectedIndexes()
        #     return [self.headermodel.itemFromIndex(i).header for i in model_indices]

    def currentheaders(self):
        selected_indices = self.selectionmodel.selectedIndexes()
        headers = []
        for model_index in selected_indices:
            headers.append(self.headermodel.itemFromIndex(model_index).header)
        return headers

    def process(self):
        workflow = self.processor.param['Algorithm']()
        data = [header.meta_array() for header in self.currentheaders()]
        labels = self.rawtabview.currentWidget().poly_mask()
        labels = [labels] * len(data)
        workflow.execute_all(None,
                             data=data,
                             labels=labels,
                             callback_slot=self.show_g2)
        # for header in self.currentheaders():
        #
        #     #             # Create start and descriptor before execution
        #     #             # self.correlationdocument = CorrelationDocument(
        #     #             #     self.currentheader(),
        #     #             #     self.fileselectionview.correlationname.text()
        #     #             # )
        #
        #     workflow.execute(data=header.meta_array(),
        #                      labels=self.rawtabview.currentWidget().poly_mask(),
        #                      callback_slot=self.show_g2)

        # workflow.execute(data=self.currentheader().meta_array(),
        #                  labels=self.rawtabview.currentWidget().poly_mask(),
        #                  callback_slot=self.show_g2)
        # workflow = self.processor.param['Algorithm']()
        # data = self.currentheader()[0].meta_array()
        # if len(self.currentheader()) > 1:
        #     data = np.array([self.currentheader()[i].meta_array() for i in self.currentheader()])
        # workflow.execute(data=data,
        #                  labels=self.rawtabview.currentWidget().poly_mask(),
        #                  callback_slot=self.show_g2)

    def show_g2(self, result):
        data = {} # TODO -- temp { 'name': Uniqueresultname, 'result': result
        if not self.fileselectionview.correlationname.displayText():
            data['name'] = self.fileselectionview.correlationname.placeholderText()
        else:
            data['name'] = self.fileselectionview.correlationname.displayText()

        # data['result'] = []
        # for data in result:
        #     data['result'] += data
        data['result'] = result

        try:
            self.correlationview.appendData(data)
            # if only a single image was selected, the value is 0 length.
            # self.correlationview.plotwidget.plot(result['g2'].value.squeeze())

            # Temporary -- just populating the combobox w/out model
            # self.correlationview.resultslist.addItem(
            #     self.currentheader().startdoc['sample_name'])
        except TypeError:
            # occurs when only 1 image is selected and then 'process' is clicked
            # i.e. not a series of images
            # TODO -- how to handle selection of non-series items?
            QMessageBox.warning(QApplication.activeWindow(),
                                'Only one image selected',
                                'Please select more than one image')
        # add event and stop to the correlation document
        # TODO -- do we need the document? Why not just add to a model?
        # self.correlationdocument.createEvent()
        # self.correlationdocument.add()


