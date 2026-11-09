Attribute VB_Name = "modCompletar"
Option Explicit
' ==========================================================================
'  Completar el modelo despues de abrir el libro.
'
'  Las consultas Agendamiento y Quiebre ya vienen cargadas tal como las guardo Excel
'  (tablas BD_Agendamiento y BD_Quiebre). Este modulo agrega, desde Excel:
'    1) las 14 columnas calculadas a la derecha de BD_Agendamiento
'    2) las 7 columnas de Datos!TDatos que dependen de ellas
'       (Pendiente SQL, Agendado, Por agendar, Q. recuperable, Q. irrecuperable,
'        Fuera de SOP, Bloqueado)
'
'  Uso:  Alt+F11 > Archivo > Importar archivo... > modCompletar.bas
'        Alt+F8  > Completar_Modelo > Ejecutar   (una sola vez; se puede repetir)
'        Alt+F8  > Verificar_Modelo              (informe del estado)
'  Despues: Datos > Actualizar todo cuando quieras traer datos nuevos.
' ==========================================================================

Private Const SH_AGE As String = "Agendamiento"
Private Const SH_QUI As String = "Quiebre"
Private Const SH_DAT As String = "Datos"
Private Const T_AGE As String = "BD_Agendamiento"
Private Const T_QUI As String = "BD_Quiebre"
Private Const T_DAT As String = "TDatos"

' ---------------------------------------------------------------- utilidades
Private Function BuscarTabla(ByVal hoja As String, ByVal nombre As String) As ListObject
    Dim ws As Worksheet, lo As ListObject
    Set ws = ThisWorkbook.Worksheets(hoja)
    For Each lo In ws.ListObjects
        If lo.Name = nombre Then
            Set BuscarTabla = lo
            Exit Function
        End If
    Next lo
    If ws.ListObjects.Count = 1 Then
        Set lo = ws.ListObjects(1)
        lo.Name = nombre
        Set BuscarTabla = lo
    End If
End Function

Private Function ColExiste(ByVal lo As ListObject, ByVal nom As String) As Boolean
    Dim lc As ListColumn
    For Each lc In lo.ListColumns
        If lc.Name = nom Then
            ColExiste = True
            Exit Function
        End If
    Next lc
End Function

' Crea la columna si no existe y le pone la formula (columna calculada)
Private Sub PonerCol(ByVal lo As ListObject, ByVal nom As String, ByVal f As String, Optional ByVal fmt As String = "")
    Dim lc As ListColumn
    If ColExiste(lo, nom) Then
        Set lc = lo.ListColumns(nom)
    Else
        Set lc = lo.ListColumns.Add
        lc.Name = nom
    End If
    If Not lc.DataBodyRange Is Nothing Then
        lc.DataBodyRange.Formula = f
        If fmt <> "" Then lc.DataBodyRange.NumberFormat = fmt
    End If
End Sub

' Referencia a la fila actual de BD_Agendamiento
Private Function RA(ByVal col As String) As String
    RA = T_AGE & "[[#This Row],[" & col & "]]"
End Function

' Suma de una columna "M$ ..." de BD_Agendamiento por Llave
Private Function FDat(ByVal colAge As String, ByVal conFactor As Boolean) As String
    FDat = "=SUMIFS(" & T_AGE & "[[" & colAge & "]]," & T_AGE & "[[Llave]],TDatos[[#This Row],[Llave]])"
    If conFactor Then FDat = FDat & "*TDatos[[#This Row],[Factor]]"
End Function

' ---------------------------------------------------------------- proceso principal
Public Sub Completar_Modelo()
    Dim loA As ListObject, loQ As ListObject, loD As ListObject
    Dim qLin As String, qIrr As String, qRec As String
    Dim paso As String, calcPrev As Long

    On Error GoTo EH
    calcPrev = Application.Calculation
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    paso = "buscar las tablas"
    Set loA = BuscarTabla(SH_AGE, T_AGE)
    Set loQ = BuscarTabla(SH_QUI, T_QUI)
    Set loD = BuscarTabla(SH_DAT, T_DAT)
    If loA Is Nothing Then Err.Raise vbObjectError + 1, , "No encuentro la tabla de la consulta en la hoja " & SH_AGE
    If loQ Is Nothing Then Err.Raise vbObjectError + 1, , "No encuentro la tabla de la consulta en la hoja " & SH_QUI
    If loD Is Nothing Then Err.Raise vbObjectError + 1, , "No encuentro la tabla " & T_DAT & " en la hoja " & SH_DAT

    qLin = "Quiebre L" & ChrW(237) & "nea"
    qIrr = "Quiebre Irrec L" & ChrW(237) & "nea"
    qRec = "Quiebre Rec L" & ChrW(237) & "nea"

    ' ---- 1) columnas calculadas de BD_Agendamiento (el orden importa: unas usan a otras)
    paso = "columna Llave"
    PonerCol loA, "Llave", "=" & RA("grupoSop") & "&" & RA("clasifPdto2")
    paso = "columna Precio M$"
    PonerCol loA, "Precio M$", "=IF(" & RA("qtySolicitado") & ">0," & RA("montoPendiente") & "/" & RA("qtySolicitado") & "/1000,0)", "#,##0.0000"
    paso = "columna " & qLin
    PonerCol loA, qLin, "=IF(" & RA("qtySinAgendar") & ">0,MIN(" & RA("qtySinAgendar") & ",SUMIFS(" & T_QUI & "[qty_total]," & T_QUI & "[pedido]," & RA("Pedido") & "," & T_QUI & "[codigoSap]," & RA("codigoSap") & ")),0)"
    paso = "columna " & qIrr
    PonerCol loA, qIrr, "=IF(" & RA(qLin) & ">0,MIN(" & RA(qLin) & ",SUMIFS(" & T_QUI & "[qty_irrecuperable]," & T_QUI & "[pedido]," & RA("Pedido") & "," & T_QUI & "[codigoSap]," & RA("codigoSap") & ")),0)"
    paso = "columna " & qRec
    PonerCol loA, qRec, "=" & RA(qLin) & "-" & RA(qIrr)
    paso = "columna Cubierto Fuera SOP"
    PonerCol loA, "Cubierto Fuera SOP", "=IF(" & RA("SALDO_SOP") & "+" & RA("Pendiente") & "<0," & RA("qtySinAgendar") & "-" & RA(qLin) & ",0)"
    paso = "columna Cubierto Dentro SOP"
    PonerCol loA, "Cubierto Dentro SOP", "=" & RA("qtySinAgendar") & "-" & RA(qLin) & "-" & RA("Cubierto Fuera SOP")
    paso = "columna M$ Pendiente"
    PonerCol loA, "M$ Pendiente", "=" & RA("qtySolicitado") & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Agendado"
    PonerCol loA, "M$ Agendado", "=" & RA("qtyAgendado") & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Bloqueado"
    PonerCol loA, "M$ Bloqueado", "=" & RA("qtyBloqMes") & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Por agendar"
    PonerCol loA, "M$ Por agendar", "=" & RA("Cubierto Dentro SOP") & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Fuera SOP"
    PonerCol loA, "M$ Fuera SOP", "=" & RA("Cubierto Fuera SOP") & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Q recuperable"
    PonerCol loA, "M$ Q recuperable", "=" & RA(qRec) & "*" & RA("Precio M$"), "#,##0.00"
    paso = "columna M$ Q irrecuperable"
    PonerCol loA, "M$ Q irrecuperable", "=" & RA(qIrr) & "*" & RA("Precio M$"), "#,##0.00"

    ' ---- 2) columnas de TDatos que dependen de BD_Agendamiento
    paso = "TDatos: Pendiente SQL"
    PonerCol loD, "Pendiente SQL", FDat("M$ Pendiente", False)
    paso = "TDatos: Agendado"
    PonerCol loD, "Agendado", FDat("M$ Agendado", True)
    paso = "TDatos: Por agendar"
    PonerCol loD, "Por agendar", FDat("M$ Por agendar", True)
    paso = "TDatos: Q. recuperable"
    PonerCol loD, "Q. recuperable", FDat("M$ Q recuperable", True)
    paso = "TDatos: Q. irrecuperable"
    PonerCol loD, "Q. irrecuperable", FDat("M$ Q irrecuperable", True)
    paso = "TDatos: Fuera de SOP"
    PonerCol loD, "Fuera de SOP", FDat("M$ Fuera SOP", True)
    paso = "TDatos: Bloqueado"
    PonerCol loD, "Bloqueado", FDat("M$ Bloqueado", True)

    paso = "calcular"
    Application.Calculation = calcPrev
    Application.CalculateFull
    Application.ScreenUpdating = True
    MsgBox "Listo. Se completaron BD_Agendamiento (" & loA.ListRows.Count & " filas) y TDatos." & vbCrLf & _
           "Ejecuta Verificar_Modelo para ver el estado.", vbInformation, "Completar modelo"
    Exit Sub

EH:
    Application.ScreenUpdating = True
    On Error Resume Next
    Application.Calculation = calcPrev
    MsgBox "Fallo en el paso: " & paso & vbCrLf & vbCrLf & Err.Description, vbExclamation, "Completar modelo"
End Sub

' ---------------------------------------------------------------- informe de estado
Private Function Distintos(ByVal lo As ListObject, ByVal col As String) As String
    Dim d As Object, v As Variant, i As Long, n As Long
    Set d = CreateObject("Scripting.Dictionary")
    If lo.DataBodyRange Is Nothing Then Distintos = "0": Exit Function
    v = lo.ListColumns(col).DataBodyRange.Value
    For i = 1 To UBound(v, 1)
        If Not IsError(v(i, 1)) Then
            If CStr(v(i, 1)) <> "" Then d(CStr(v(i, 1))) = 1
        End If
    Next i
    Distintos = CStr(d.Count)
End Function

Public Sub Verificar_Modelo()
    Dim loA As ListObject, loQ As ListObject, loD As ListObject
    Dim t As String, faltan As String, nm As Variant, lista As Variant

    On Error GoTo EH
    Set loA = BuscarTabla(SH_AGE, T_AGE)
    Set loQ = BuscarTabla(SH_QUI, T_QUI)
    Set loD = BuscarTabla(SH_DAT, T_DAT)
    If loA Is Nothing Or loQ Is Nothing Or loD Is Nothing Then
        MsgBox "No encuentro alguna de las tablas (BD_Agendamiento, BD_Quiebre, TDatos).", vbExclamation, "Verificar modelo"
        Exit Sub
    End If

    t = "Consultas" & vbCrLf & _
        "  BD_Agendamiento: " & loA.ListRows.Count & " filas" & vbCrLf & _
        "  BD_Quiebre:      " & loQ.ListRows.Count & " filas" & vbCrLf & vbCrLf

    lista = Array("Llave", "Precio M$", "Quiebre L" & ChrW(237) & "nea", "Quiebre Irrec L" & ChrW(237) & "nea", _
                  "Quiebre Rec L" & ChrW(237) & "nea", "Cubierto Fuera SOP", "Cubierto Dentro SOP", "M$ Pendiente", _
                  "M$ Agendado", "M$ Bloqueado", "M$ Por agendar", "M$ Fuera SOP", "M$ Q recuperable", "M$ Q irrecuperable")
    For Each nm In lista
        If Not ColExiste(loA, CStr(nm)) Then faltan = faltan & "  - " & nm & vbCrLf
    Next nm
    If faltan = "" Then
        t = t & "Columnas calculadas de BD_Agendamiento: 14 de 14" & vbCrLf & vbCrLf
    Else
        t = t & "Faltan columnas en BD_Agendamiento (ejecuta Completar_Modelo):" & vbCrLf & faltan & vbCrLf
    End If

    t = t & "Valores para las segmentaciones (TDatos)" & vbCrLf & _
        "  Negocio: " & Distintos(loD, "Negocio") & "   Grupo: " & Distintos(loD, "Grupo") & _
        "   Cliente: " & Distintos(loD, "Cliente") & vbCrLf & _
        "  Clasificacion: " & Distintos(loD, ChrW(67) & "lasificaci" & ChrW(243) & "n") & _
        "   KAM: " & Distintos(loD, "KAM") & "   LCM: " & Distintos(loD, "LCM") & vbCrLf & vbCrLf & _
        "Totales (M$)  SOP: " & Format(Application.WorksheetFunction.Sum(loD.ListColumns("SOP").DataBodyRange), "#,##0") & _
        "   Agendado: " & Format(Application.WorksheetFunction.Sum(loD.ListColumns("Agendado").DataBodyRange), "#,##0")
    MsgBox t, vbInformation, "Verificar modelo"
    Exit Sub
EH:
    MsgBox "No pude completar la verificacion: " & Err.Description, vbExclamation, "Verificar modelo"
End Sub
