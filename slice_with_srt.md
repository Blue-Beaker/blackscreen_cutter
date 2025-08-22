生成字幕文件后, 可使用`make_slices.py`继续按分好的段切分视频, 并以单独视频文件或文本的形式导出.
dump参数可输入一个文本模板. 不指定此参数则使用ffmpeg输出切好的视频. 
`make_slices.py [--dump=DUMP_TEMPLATE_FILE] [--length=MAX_LENGTH] [--end_offset=END_OFFSET] VIDEO_FILE`
使用示例:
```
generate_sections.py 'video_to_crop.mkv' --dump='dump_template.txt' --length=500 > dump2.txt
```
dump_template.txt包含了一个示例,可生成适用于kdenlive项目文件的分段部分. 用文本编辑器打开项目文件可以找到分段应该放在哪. 

After generating the subtitle file, `make_slices.py` can be used to slice the video with the sections, and export to video slices or templated text.
The dump option can be used to load a text template. Or sliced videos will be exported directly with ffmpeg in your PATH. 
`make_slices.py [--dump=DUMP_TEMPLATE_FILE] [--length=MAX_LENGTH] [--end_offset=END_OFFSET] VIDEO_FILE`
Example:
```
generate_sections.py 'video_to_crop.mkv' --dump='dump_template.txt' --length=500 > dump2.txt
```
An example is included in dump_template.txt, that can generate sections for kdenlive project file. Open the project file with a text editor to find it out. 