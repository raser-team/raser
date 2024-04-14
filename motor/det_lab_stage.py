#! /usr/bin/env python

# Reference:
# Luis Ardila 	leardilap@unal.edu.co 	22/03/15
import sys
from PyQt5 import QtGui, QtCore, uic, QtWidgets

tctEnable = True
if tctEnable:
    import pymotor

testPass = False

class Axis(QtWidgets.QWidget):
    def __init__(self, parent, Title, Device, uiFile):
        super(Axis, self).__init__(parent)

        self.ui = uic.loadUi(uiFile)

        #Declaring Device
        if tctEnable:
            self.axis = pymotor.Motor(Device)

        #Jogging Plus
        self.ui.JogPlus.pressed.connect(self.JogPlus)
        self.ui.JogPlus.released.connect(self.Stop)

        #Jogging Minus
        self.ui.JogMinus.pressed.connect(self.JogMinus)
        self.ui.JogMinus.released.connect(self.Stop)

        #Home
        self.ui.Home.clicked.connect(self.Home)

        #Move
        self.ui.MoveAB.clicked.connect(self.MoveAB)
        self.ui.MoveRE.clicked.connect(self.MoveRE)

        ##Stop
        self.ui.Stop.clicked.connect(self.Stop)

        ##Limits
        self.ui.Limits.clicked.connect(self.Limits)

        #Scroll
        self.ui.Scroll.valueChanged[int].connect(self.UpdateDesiredPosScroll)

        #Updating State - Position
        self.timer = QtCore.QTimer()
        self.timer.start(100)
        self.timer.timeout.connect(self.UpdateState)
        self.timer.timeout.connect(self.CurrentPosition)

        #####################
        # Initializing Widget
        self.UpdateDesiredPos()
        self.ui.setWindowTitle(Title)

        # Var
        self.currentPos = 0
        self.Title = Title
        self.lenght = self.ui.DesirePos.maximum()

    def JogPlus(self):
        if tctEnable:
            self.axis.moveforward()
        else:
            self.ui.StatusLabel.setText("JogPlus")

    def JogMinus(self):
        if tctEnable:
            self.axis.movebackward()
        else:
            self.ui.StatusLabel.setText("JogMinus")

    def Home(self):
        ret = QtWidgets.QMessageBox.warning(self, "Homming",
                "Please Check the setup!\n\nAre you sure you really want\nto Home the motor?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Escape)
        if ret == QtWidgets.QMessageBox.Yes:
            if tctEnable:
                self.axis.home()
            else:
                self.ui.StatusLabel.setText("Home")

    def Stop(self):
        if tctEnable:
            self.axis.stop()
        else:
            self.ui.StatusLabel.setText("")

        self.UpdateDesiredPos()

    def Limits(self):
        self.Limits = Limits(self)

    def MoveAB(self):
        pos = self.ui.DesirePos.value()
        if tctEnable:
            self.axis.move(pos)
            self.ui.CurrentPos.display(self.currentPos)
        else:
            self.ui.StatusLabel.setText(str(pos))
            self.currentPos = self.ui.DesirePos.value()
            self.ui.CurrentPos.display(self.currentPos)

        self.ui.Scroll.setValue(pos)

    def MoveRE(self):
        movement = self.ui.RelativePos.value()
        UpperLimit = self.ui.DesirePos.maximum()
        LowerLimit = self.ui.DesirePos.minimum()

        if self.currentPos + movement > UpperLimit:
            movement = UpperLimit - self.currentPos
        elif self.currentPos + movement < LowerLimit:
            movement = LowerLimit - self.currentPos

        if tctEnable:
            self.axis.forward(movement)
        else:
            self.ui.StatusLabel.setText(str(movement))
            self.currentPos = self.currentPos + movement
            self.ui.CurrentPos.display(self.currentPos)

        self.UpdateDesiredPos()

    def UpdateDesiredPosScroll(self):
        pos = self.ui.Scroll.value()
        self.ui.DesirePos.setValue(pos)

    def UpdateDesiredPos(self):
        if tctEnable:
            pos = self.axis.get_status_position()
            self.ui.DesirePos.setValue(pos)
            self.ui.Scroll.setValue(pos)

    def CurrentPosition(self):
        if tctEnable:
            self.currentPos = self.axis.get_status_position()
            self.ui.CurrentPos.display(self.currentPos)

    def UpdateState(self):
        if tctEnable and testPass:
            state = self.axis.state()
            self.ui.StatusLabel.setText(str(state))

    def run(self):
        self.ui.show()

class Limits(QtWidgets.QDialog):
    def __init__(self, parent):
        QtWidgets.QDialog.__init__(self, parent)

        # Declaring GUI
        self.ui = uic.loadUi('GUI/Limits.ui')
        self.ui.show()
        self.ui.ButtonBox.accepted.connect(lambda: self.Accepted)
        self.ui.UpperLimit.valueChanged.connect(lambda: self.UpdateUpperLimit)
        self.ui.LowerLimit.valueChanged.connect(lambda: self.UpdateLowerLimit)
        self.ui.setWindowTitle(str(parent.Title + " Limits"))
        self.ui.UpperLimit.setMaximum(parent.lenght*2)
        self.ui.LowerLimit.setMaximum(parent.lenght*2)
        self.ui.UpperLimit.setMinimum(-parent.lenght*2)
        self.ui.LowerLimit.setMinimum(-parent.lenght*2)
        self.ui.UpperLimit.setValue(parent.ui.DesirePos.maximum())
        self.ui.LowerLimit.setValue(parent.ui.DesirePos.minimum())

    def UpdateUpperLimit(self, parent):
        self.UpperLimit = self.ui.UpperLimit.value()
        self.LowerLimit = self.ui.LowerLimit.value()
        if self.UpperLimit - self.LowerLimit > parent.lenght:
            self.ui.LowerLimit.setValue(self.UpperLimit - parent.lenght)
        elif self.UpperLimit <= self.LowerLimit:
            self.ui.LowerLimit.setValue(self.UpperLimit - 1)

    def UpdateLowerLimit(self, parent):
        self.UpperLimit = self.ui.UpperLimit.value()
        self.LowerLimit = self.ui.LowerLimit.value()
        if self.LowerLimit + parent.lenght < self.UpperLimit:
            self.ui.UpperLimit.setValue(self.LowerLimit + parent.lenght)
        elif self.LowerLimit >= self.UpperLimit:
            self.ui.UpperLimit.setValue(self.LowerLimit + 1)

    def Accepted(self, parent):
        parent.ui.DesirePos.setMaximum(self.ui.UpperLimit.value())
        parent.ui.DesirePos.setMinimum(self.ui.LowerLimit.value())
        parent.ui.Scroll.setMaximum(self.ui.UpperLimit.value())
        parent.ui.Scroll.setMinimum(self.ui.LowerLimit.value())

class MainWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MainWidget, self).__init__(parent)

        self.stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.stack)

        ##############################################################
        # DETECTOR
        # X Detector
        XD_Title = "X Detector"
        XD_Device = "testxdet"
        #XD_Device = "xi-com:///dev/tty.usbmodem00000D81"
        XD_uiFile = "GUI/XWidget.ui"
        self.XDetector = Axis(self, XD_Title, XD_Device, XD_uiFile)

        ## Y Detector
        #YD_Title = "Y Detector"
        #YD_Device = "testydet"
        #YD_uiFile = "GUI/YWidget.ui"
        #self.YDetector = Axis(self, YD_Title, YD_Device, YD_uiFile)

        ## Z Detector
        #ZD_Title = "Z Detector"
        #ZD_Device = "testzdet"
        #ZD_uiFile = "GUI/ZWidget.ui"
        #self.ZDetector = Axis(self, ZD_Title, ZD_Device, ZD_uiFile)

        ################################################################
        # MAIN WINDOW
        self.stack.addWidget(self.XDetector)
        #self.stack.addWidget(self.YDetector)
        #self.stack.addWidget(self.ZDetector)

        self.XDetector.run()
        #self.YDetector.run()
        #self.ZDetector.run()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    win = MainWidget()

    sys.exit(app.exec_())
