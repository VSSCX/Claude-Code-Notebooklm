Attribute VB_Name = "modSeguimiento"
Option Explicit
' ==========================================================================
'  Seguimiento por reunion
'
'  Crea la hoja "Seguimiento": una fecha por cada reunion cerrada y, debajo de cada
'  fecha, los 4 indicadores:
'      % Facturado | % Fact + Pend (R+P) | % Cierre proyectado | % Cierre Net
'  para el TOTAL y por KAM, por Cliente y por Clasificacion.
'
'  Los datos salen de la hoja Registro (tabla TRegistro), donde Cerrar reunion guarda la foto.
'  La hoja son formulas: cada cierre nuevo agrega su fecha solo.
'
'  Instalacion (una vez):
'     Alt+F11 > Archivo > Importar archivo... > modSeguimiento.bas
'     Alt+F8  > Crear_Seguimiento > Ejecutar
'  Eso ademas conecta el boton "Cerrar reunion" de Resumen para que, al cerrar,
'  la hoja se actualice sola (el boton sigue haciendo lo mismo de antes).
' ==========================================================================

Private Const SH_SEG As String = "Seguimiento"
Private Const SH_REG As String = "Registro"
Private Const T_REG As String = "TRegistro"
Private Const N_SLOTS As Long = 26          ' reuniones que caben (26 = medio ano semanal)
Private Const COL0 As Long = 3              ' primera columna de datos (C)
Private Const R_FECHA As Long = 5           ' fila de las fechas
Private Const R_SUB As Long = 6             ' fila de los indicadores
Private Const R_TOT As Long = 7             ' fila TOTAL

' ---------------------------------------------------------------- utilidades
Private Function ColL(ByVal n As Long) As String
    ColL = Split(ThisWorkbook.Worksheets(1).Cells(1, n).Address(True, False), "$")(0)
End Function

Private Function Cla() As String
    Cla = "Clasificaci" & ChrW(243) & "n"
End Function

Private Function ObtenerRegistro() As ListObject
    Dim lo As ListObject
    On Error Resume Next
    Set lo = ThisWorkbook.Worksheets(SH_REG).ListObjects(T_REG)
    On Error GoTo 0
    If lo Is Nothing Then Err.Raise vbObjectError + 1, , "No encuentro la tabla " & T_REG & " en la hoja " & SH_REG
    Set ObtenerRegistro = lo
End Function

Private Function HojaSeg() As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SH_SEG)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(1))
        ws.Name = SH_SEG
    End If
    Set HojaSeg = ws
End Function

' Valores distintos de una columna de TRegistro, ordenados A-Z
Private Function ListaUnica(ByVal lo As ListObject, ByVal col As String) As Variant
    Dim d As Object, v As Variant, i As Long, j As Long, s As String, a As Variant, t As Variant
    Set d = CreateObject("Scripting.Dictionary")
    d.CompareMode = 1
    If Not lo.DataBodyRange Is Nothing Then
        If lo.ListRows.Count = 1 Then
            ReDim v(1 To 1, 1 To 1)
            v(1, 1) = lo.ListColumns(col).DataBodyRange.Value
        Else
            v = lo.ListColumns(col).DataBodyRange.Value
        End If
        For i = 1 To UBound(v, 1)
            If Not IsError(v(i, 1)) Then
                s = Trim$(CStr(v(i, 1)))
                If s <> "" Then
                    If Not d.Exists(s) Then d.Add s, 1
                End If
            End If
        Next i
    End If
    If d.Count = 0 Then
        ListaUnica = Array()
        Exit Function
    End If
    a = d.Keys
    For i = LBound(a) To UBound(a) - 1
        For j = i + 1 To UBound(a)
            If StrComp(CStr(a(j)), CStr(a(i)), vbTextCompare) < 0 Then
                t = a(i): a(i) = a(j): a(j) = t
            End If
        Next j
    Next i
    ListaUnica = a
End Function

' Indicadores: 0 % Facturado, 1 % R+P, 2 % Cierre proyectado, 3 % Cierre Net
Private Function MetTitulo(ByVal j As Long) As String
    Select Case j
        Case 0: MetTitulo = "% Facturado"
        Case 1: MetTitulo = "% Fact + Pend (R+P)"
        Case 2: MetTitulo = "% Cierre proyectado"
        Case Else: MetTitulo = "% Cierre Net"
    End Select
End Function

Private Function MetNum(ByVal j As Long) As String
    Select Case j
        Case 0: MetNum = "Facturado"
        Case 1: MetNum = "R+P"
        Case 2: MetNum = "Cierre"
        Case Else: MetNum = "Cierre Net"
    End Select
End Function

Private Function MetDen(ByVal j As Long) As String
    If j = 3 Then MetDen = "SOP Net" Else MetDen = "SOP"
End Function

' % = suma del numerador / suma del denominador, para la fecha de la columna y (opcional) un KAM/Cliente/Clasificacion
Private Function FRatio(ByVal fecha As String, ByVal j As Long, ByVal critCol As String, ByVal critRef As String) As String
    Dim c As String, s1 As String, s2 As String
    c = T_REG & "[[Fecha]]," & fecha
    If critCol <> "" Then c = c & "," & T_REG & "[[" & critCol & "]]," & critRef
    s1 = "SUMIFS(" & T_REG & "[[" & MetNum(j) & "]]," & c & ")"
    s2 = "SUMIFS(" & T_REG & "[[" & MetDen(j) & "]]," & c & ")"
    FRatio = "=IF(" & fecha & "="""","""",IFERROR(" & s1 & "/" & s2 & ",""""))"
End Function

Private Sub EscribirFila(ByVal ws As Worksheet, ByVal r As Long, ByVal critCol As String)
    Dim f() As Variant, k As Long, j As Long, fecha As String
    ReDim f(1 To 1, 1 To 4 * N_SLOTS)
    For k = 1 To N_SLOTS
        fecha = "$" & ColL(COL0 + (k - 1) * 4) & "$" & R_FECHA
        For j = 0 To 3
            f(1, (k - 1) * 4 + j + 1) = FRatio(fecha, j, critCol, "$B" & r)
        Next j
    Next k
    ws.Range(ws.Cells(r, COL0), ws.Cells(r, COL0 + 4 * N_SLOTS - 1)).Formula = f
End Sub

' Banda de seccion + una fila por elemento. Devuelve la siguiente fila libre.
Private Function Bloque(ByVal ws As Worksheet, ByVal r As Long, ByVal titulo As String, ByVal critCol As String, ByVal items As Variant) As Long
    Dim i As Long, ult As Long
    ult = COL0 + 4 * N_SLOTS - 1
    ws.Cells(r, 2).Value = titulo
    With ws.Range(ws.Cells(r, 2), ws.Cells(r, ult))
        .Interior.Color = RGB(232, 237, 244)
        .Font.Bold = True
        .Font.Color = RGB(11, 42, 91)
    End With
    r = r + 1
    For i = LBound(items) To UBound(items)
        ws.Cells(r, 2).Value = items(i)
        ws.Cells(r, 2).IndentLevel = 1
        EscribirFila ws, r, critCol
        With ws.Range(ws.Cells(r, 2), ws.Cells(r, ult)).Borders(9)
            .LineStyle = 1
            .Color = RGB(199, 205, 214)
            .Weight = 1
        End With
        r = r + 1
    Next i
    Bloque = r + 1
End Function

' ---------------------------------------------------------------- construccion
Private Sub Construir(ByVal volver As Boolean)
    Dim lo As ListObject, ws As Worksheet, wsPrev As Worksheet
    Dim k As Long, j As Long, c0 As Long, r As Long, ult As Long, ultFila As Long
    Dim calcPrev As Long, paso As String, nFechas As Long, REU As String
    Dim lk As Variant, lc As Variant, lcl As Variant

    On Error GoTo EH
    calcPrev = Application.Calculation
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    Set wsPrev = ActiveSheet
    REU = "reuni" & ChrW(243) & "n"

    paso = "buscar Registro"
    Set lo = ObtenerRegistro()
    lk = ListaUnica(lo, "KAM")
    lc = ListaUnica(lo, "Cliente")
    lcl = ListaUnica(lo, Cla())

    paso = "preparar la hoja"
    Set ws = HojaSeg()
    ws.Activate
    On Error Resume Next
    ActiveWindow.FreezePanes = False
    On Error GoTo EH
    ws.Cells.Clear
    ws.Columns.Hidden = False
    ult = COL0 + 4 * N_SLOTS - 1

    paso = "titulo"
    ws.Cells(1, 2).Value = "Seguimiento por " & REU
    ws.Cells(2, 2).Value = "Cada " & REU & " cerrada agrega su fecha. Fuente: hoja Registro (foto de Cerrar " & REU & "). " & _
                           "% sobre SOP; % Cierre Net sobre SOP Net."
    With ws.Range(ws.Cells(1, 2), ws.Cells(2, ult))
        .Interior.Color = RGB(11, 42, 91)
        .Font.Color = RGB(255, 255, 255)
    End With
    ws.Cells(1, 2).Font.Size = 16
    ws.Cells(1, 2).Font.Bold = True
    ws.Rows(1).RowHeight = 30
    ws.Cells(2, 2).Font.Size = 9
    ws.Cells(2, 2).Font.Color = RGB(190, 200, 215)

    paso = "fechas"
    ws.Cells(R_FECHA, 2).Value = "Fecha de la " & REU
    ws.Cells(R_SUB, 2).Value = "Indicador"
    For k = 1 To N_SLOTS
        c0 = COL0 + (k - 1) * 4
        If k = 1 Then
            ws.Cells(R_FECHA, c0).Formula = "=IFERROR(1/(1/MIN(" & T_REG & "[[Fecha]])),"""")"
        Else
            ws.Cells(R_FECHA, c0).Formula = "=IF(" & ws.Cells(R_FECHA, c0 - 4).Address(False, False) & "="""","""",IFERROR(1/(1/MINIFS(" & _
                T_REG & "[[Fecha]]," & T_REG & "[[Fecha]],"">""&" & ws.Cells(R_FECHA, c0 - 4).Address(False, False) & ")),""""))"
        End If
        ws.Cells(R_FECHA, c0).NumberFormat = "dd-mm-yyyy"
        For j = 0 To 3
            ws.Cells(R_SUB, c0 + j).Value = MetTitulo(j)
        Next j
        With ws.Range(ws.Cells(R_FECHA, c0), ws.Cells(R_FECHA, c0 + 3))
            .HorizontalAlignment = 7            ' centrar en la seleccion
        End With
    Next k
    With ws.Range(ws.Cells(R_FECHA, 2), ws.Cells(R_FECHA, ult))
        .Interior.Color = RGB(11, 42, 91)
        .Font.Color = RGB(255, 255, 255)
        .Font.Bold = True
        .Font.Size = 12
    End With
    ws.Rows(R_FECHA).RowHeight = 24
    With ws.Range(ws.Cells(R_SUB, 2), ws.Cells(R_SUB, ult))
        .Interior.Color = RGB(52, 73, 94)
        .Font.Color = RGB(255, 255, 255)
        .Font.Bold = True
        .Font.Size = 9
        .WrapText = True
        .HorizontalAlignment = -4108
        .VerticalAlignment = -4108
    End With
    ws.Cells(R_SUB, 2).HorizontalAlignment = -4131
    ws.Rows(R_SUB).RowHeight = 32

    paso = "total"
    ws.Cells(R_TOT, 2).Value = "TOTAL (todas las llaves)"
    EscribirFila ws, R_TOT, ""
    With ws.Range(ws.Cells(R_TOT, 2), ws.Cells(R_TOT, ult))
        .Interior.Color = RGB(232, 237, 244)
        .Font.Bold = True
        .Font.Color = RGB(11, 42, 91)
        .Borders(8).LineStyle = 1
        .Borders(9).LineStyle = 1
    End With

    paso = "por KAM / Cliente / Clasificacion"
    r = R_TOT + 2
    r = Bloque(ws, r, "POR KAM", "KAM", lk)
    r = Bloque(ws, r, "POR CLIENTE", "Cliente", lc)
    r = Bloque(ws, r, "POR CLASIFICACI" & ChrW(211) & "N", Cla(), lcl)
    ultFila = r - 2

    paso = "formato"
    ws.Range(ws.Cells(R_TOT, COL0), ws.Cells(ultFila, ult)).NumberFormat = "0.0%"
    ws.Range(ws.Cells(R_TOT, COL0), ws.Cells(ultFila, ult)).HorizontalAlignment = -4152
    ws.Columns(1).ColumnWidth = 1.5
    ws.Columns(2).ColumnWidth = 38
    ws.Range(ws.Columns(COL0), ws.Columns(ult)).ColumnWidth = 11
    For k = 1 To N_SLOTS
        c0 = COL0 + (k - 1) * 4
        With ws.Range(ws.Cells(R_FECHA, c0), ws.Cells(ultFila, c0)).Borders(7)
            .LineStyle = 1
            .Color = RGB(174, 182, 191)
            .Weight = 2
        End With
    Next k
    ws.Tab.Color = RGB(11, 42, 91)
    ws.Cells(3, 2).Formula = "=IF(COUNT(" & ws.Range(ws.Cells(R_FECHA, COL0), ws.Cells(R_FECHA, ult)).Address & ")=0," & _
        """Aun no hay reuniones cerradas en Registro.""," & _
        "IF(MAX(" & T_REG & "[[Fecha]])>MAX(" & ws.Range(ws.Cells(R_FECHA, COL0), ws.Cells(R_FECHA, ult)).Address & ")," & _
        """Atencion: hay reuniones mas recientes que las columnas disponibles."",""""))"
    ws.Cells(3, 2).Font.Color = RGB(192, 57, 43)
    ws.Cells(3, 2).Font.Bold = True

    paso = "calcular"
    Application.Calculation = calcPrev
    Application.Calculate

    paso = "ocultar columnas sin fecha"
    nFechas = 0
    For k = 1 To N_SLOTS
        c0 = COL0 + (k - 1) * 4
        If Not IsError(ws.Cells(R_FECHA, c0).Value) Then
            If CStr(ws.Cells(R_FECHA, c0).Value) = "" Then
                ws.Range(ws.Columns(c0), ws.Columns(c0 + 3)).Hidden = True
            Else
                nFechas = nFechas + 1
            End If
        End If
    Next k

    paso = "inmovilizar paneles"
    ws.Activate
    ActiveWindow.DisplayGridlines = False
    ActiveWindow.Zoom = 90
    ActiveWindow.ScrollRow = 1
    ActiveWindow.ScrollColumn = 1
    ws.Cells(R_TOT + 1, COL0).Select
    ActiveWindow.FreezePanes = True
    ws.Cells(R_TOT + 2, 2).Select

    paso = "conectar el boton"
    ConectarBoton

    If volver Then
        If Not wsPrev Is Nothing Then wsPrev.Activate
    End If
    Application.ScreenUpdating = True
    If Not volver Then
        MsgBox "Hoja Seguimiento lista: " & nFechas & " " & REU & "(es) registrada(s)." & vbCrLf & _
               "Al cerrar cada " & REU & " con el boton de Resumen, se agrega la fecha sola.", vbInformation, "Seguimiento"
    End If
    Exit Sub

EH:
    Application.ScreenUpdating = True
    On Error Resume Next
    Application.Calculation = calcPrev
    MsgBox "Fallo en el paso: " & paso & vbCrLf & vbCrLf & Err.Description, vbExclamation, "Seguimiento"
End Sub

' ---------------------------------------------------------------- macros publicas
Public Sub Crear_Seguimiento()
    Construir False
End Sub

Public Sub Actualizar_Seguimiento()
    Construir False
End Sub

' Hace lo mismo que el boton "Cerrar reunion" y despues actualiza el seguimiento
Public Sub Cerrar_y_Seguimiento()
    On Error GoTo EH
    Application.Run "CerrarReunion"
    On Error GoTo 0
    Construir True
    Exit Sub
EH:
    MsgBox "No pude ejecutar Cerrar reunion: " & Err.Description, vbExclamation, "Seguimiento"
End Sub

' Asigna al boton "Cerrar reunion" de Resumen la macro Cerrar_y_Seguimiento
Public Sub ConectarBoton()
    On Error Resume Next
    ThisWorkbook.Worksheets("Resumen").Shapes("btnCerrar").OnAction = "Cerrar_y_Seguimiento"
    On Error GoTo 0
End Sub
