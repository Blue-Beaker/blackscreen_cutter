## Blackscreen Cutter

可以帮助剪辑某些游戏的视频的工具.  
本工具根据视频中的黑屏部分进行分段, 并生成带分段编号的字幕. 保存的字幕文件可以导入剪辑软件用于参考.  

依赖:
```
PyQt5>=5.15.10  
pymediainfo>=6.1.0  
python3-opencv  
```

GUI版本: 用Python3打开 `cut_tool_ui.py`, 拖入视频文件然后点开始即可.  

1.基于黑屏检测的自动分段生成
生成的字幕文件会生成在视频的位置, 并加上`.srt`扩展名. 单线程版处理时实时更新字幕文件, 多线程版只有处理完才会生成字幕文件.  

2.基于差异检测的关卡改变检测
需要使用以上功能1生成的分段字幕文件. 本过程会遍历所有分段, 只保留分段开始某帧与后一段对应帧有一定差异的分段, 达到自动找出关卡改变时间的效果. 此功能生成的字幕文件为`<原文件名>_diff.srt`  

3.日志
以上两个功能会输出一些日志可供查看工作情况, 在此查看.  

4.配置
配置保存在工具同文件夹下的`cut_tool_config.json`文件内, 打开自动加载, 退出程序自动保存. 也可以将配置文件复制到别处, 拖入该标签页加载.  
配置项说明:
- 检测范围: 控制用于检测的范围  
- 预览图像: 处理时显示处理过程, 方便调试参数, 会变慢  
黑屏检测配置项:
- 黑色判定阈值: 黑屏检测时小于此值的颜色判定为黑色  
- 黑屏开始/结束百分比: 黑色占比超过此值判定为黑屏
差异检测配置: 
- 时间偏移: 每个分段从分段开始偏移此时长取一帧和其他分段对比
- 从差值减去: 差值小于此值的像素会被认为相等
- 差异值: 差异值大于此值会判定为切面

命令行版本: `cut_threaded.py [视频文件]` 多线程处理  
或者 `cut.py [视频文件]` 单线程  
建议根据自己设备上的测试结果调整线程数变量以获得更快处理速度.  


A tool to help cutting videos of some video games.  
This tool generates sections from black screens in a video, then saves the sections to a subtitle file. The saved subtitle file can be imported to a video editor as reference.  

Requirements:
```
PyQt5>=5.15.10
pymediainfo>=6.1.0
python3-opencv
```

GUI Version: Just run `cut_tool_ui.py` with python3, then drag videos into it.  
The subtitle will be generated in where the video is at, with a `.srt` extension.  

Command-line version: `cut_threaded.py [VIDEO FILE]` (multi-threaded)  
or `cut.py [VIDEO FILE]` (single-threaded)  
Change the 'THREADS' variable is recommended for better speed.  


