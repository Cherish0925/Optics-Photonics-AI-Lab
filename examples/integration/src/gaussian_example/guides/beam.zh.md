# 理想高斯光束

`gaussian-example/propagate` 适用于均匀介质中的近轴传播。
`wavelength_um` 为介质中的波长，`waist_um` 为束腰处场振幅的 1/e 半径，
`distance_mm` 为相对束腰的有符号距离。有孔径、界面、像差或强聚焦时，
应改用相应的波动求解器。束腰处波前为平面，波前半径返回 `null`，
光束半径与 Gouy 相位仍然有定义。

`software_details(tool="gaussian-example", program="propagate")` 返回所有默认输入；
需要修改程序时再请求 `source=true`。结果字段写明长度单位，
并将光束半径与复光束参数给出的值比较。
