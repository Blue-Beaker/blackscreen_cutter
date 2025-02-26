#! /bin/python3
import math
import sys,os,traceback
from PyQt5 import QtWidgets,uic
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


class Section:
    def __init__(self,start:int,end:int) -> None:
        self.start:int=start
        self.end:int=end
    def __repr__(self) -> str:
        return self.__str__()
    def __str__(self) -> str:
        return f"{self.start}ms -> {self.end}ms"

def parse_srt_time(line:str)->int:
    try:
        split1=line.strip().split(',')
        hour=0
        minutes=0
        seconds=0
        milliseconds=0

        if(split1.__len__()>=2):
            milliseconds=int(split1[1])
            line=split1[0]

        split=line.strip().split(':')
        if(split.__len__()>=3):
            hour=int(split[0])
            minutes=int(split[1])
            seconds=int(split[2])
        elif(split.__len__()>=2):
            minutes=int(split[0])
            seconds=int(split[1])
        return hour*3600000+minutes*60000+seconds*1000+milliseconds
    except:
        return -1

def parse_srt(lines:list[str])->list[Section]:
    sections:list[Section]=[]
    lastID=0

    for line in lines:
        try:
            lastID=int(line.strip())
        except:
            pass

        if '-->' in line:
            split=line.split('-->')
            if(split.__len__()>=2):
                start=parse_srt_time(split[0].strip())
                end=parse_srt_time(split[1].strip())
                sections.append(Section(start=start,end=end))
    return sections

def to_hhmmssms_time(total_time_ms:int)->str:
    minutes='{:02d}'.format(math.floor(total_time_ms/60000))
    seconds='{:02d}'.format(math.floor(total_time_ms/1000)%60)
    milliseconds='{:03d}'.format(total_time_ms%1000)
    return f"{minutes}:{seconds}.{milliseconds}"

def to_hhmmssframe_time(total_time_ms:int,fps:int)->str:
    minutes='{:02d}'.format(math.floor(total_time_ms/60000))
    seconds='{:02d}'.format(math.floor(total_time_ms/1000)%60)
    frames='{:02d}'.format(math.floor(fps/(total_time_ms%1000)))
    return f"{minutes}:{seconds}.{frames}"

def dump_section(section:Section,replacement:str)->str:
    return replacement.replace('{starttime}',to_hhmmssms_time(section.start)).replace('{endtime}',to_hhmmssms_time(section.end)).replace('{length}',to_hhmmssms_time(section.end-section.start))

def fill_slices(filePath:str,dump_template:str, max_length:int, end_offset:int) -> str:
    srtpath=filePath+".srt"
    outstr=""
    with open(srtpath,"r") as srtFile:
        sections=parse_srt(srtFile.readlines())
    for i in range(sections.__len__()):
        section=sections[i]
        section.end=section.end+end_offset
        if(max_length>0):
            section.start=max(section.start,section.end-max_length)
        if(section.start<section.end):
            outstr=outstr+dump_section(section,dump_template)
    return outstr

class App(QtWidgets.QMainWindow):
    openFileButton:QToolButton
    fileNameEdit:QLineEdit
    convertButton:QPushButton
    templateInput:QTextEdit
    textOuput:QTextEdit
    verticalLayout:QVBoxLayout
    inputLength:QSpinBox
    inputOffset:QSpinBox
    def __init__(self):
        super(App, self).__init__()
        uic.loadUi(os.path.join(sys.path[0],"slicer.ui"), self)
        self.templateInput.setText("""<entry in="{starttime}" out="{endtime}" producer="chain0">
<property name="kdenlive:id">5</property>
</entry>
""")
        assert isinstance(self.openFileButton,QToolButton)
        assert isinstance(self.convertButton,QPushButton)
        assert isinstance(self.verticalLayout,QVBoxLayout)
        self.openFileButton.clicked.connect(self.open_file)
        self.convertButton.clicked.connect(self.do_convert)


    def open_file(self):
        assert isinstance(self.fileNameEdit,QLineEdit)
        dialog=QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)

        if dialog.exec():
            files=dialog.selectedFiles()
            self.fileNameEdit.setText(files[0])


    def do_convert(self):
        assert isinstance(self.fileNameEdit,QLineEdit)
        assert isinstance(self.templateInput,QTextEdit)
        assert isinstance(self.inputLength,QSpinBox)
        assert isinstance(self.inputOffset,QSpinBox)
        assert isinstance(self.textOuput,QTextEdit)
        filepath=self.fileNameEdit.text()
        output=fill_slices(filepath,self.templateInput.toPlainText(),self.inputLength.value(),self.inputOffset.value())
        self.textOuput.setText(output)
        
app = QApplication(sys.argv)
window = App()
try:
    window.show()
    app.exec()
finally:
    pass
