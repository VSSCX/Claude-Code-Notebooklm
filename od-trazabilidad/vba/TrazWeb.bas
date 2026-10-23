Attribute VB_Name = "TrazWeb"
Option Explicit

' =========================================================
' TrazWeb.bas - Puente hacia la web de trazabilidad
'
' Arma un "paquete" JSON con lo que el flujo acaba de hacer
' (pedido, entregas, grupos, fecha SAP) y:
'   1) lo envia a la plataforma (POST API_URL)
'   2) si no hay conexion, lo copia al portapapeles -> en la web: Ctrl+V
'   3) siempre guarda una copia en <carpeta del libro>\Trazabilidad_Web\*.json
'
' No toca SAP. Cualquier error se ignora para no cortar el flujo.
'
' Enganches (una linea cada uno):
'   Extraer_Picking_NAVBTN          -> TrazWeb_Exportar "pedido"
'   VL01N_CrearEntregas_Todos...    -> TrazWeb_Exportar "entregas"
'   CrearGruposTransporte           -> TrazWeb_Exportar "grupos"
'   ActualizarFechaYReferencia      -> TrazWeb_Exportar "fecha_sap", gOk
' =========================================================

Private Const SH_IN      As String = "01_Entrada"
Private Const SH_POS     As String = "02_Posiciones"
Private Const SH_CUB     As String = "03_PedidoCubicado"
Private Const FILA_INI   As Long = 6
Private Const FILA_FIN   As Long = 27
Private Const CARPETA    As String = "Trazabilidad_Web"
Private Const API_URL    As String = "http://127.0.0.1:8000/api/paquetes"

' 01_Entrada, detalle de entregas
Private Const C_ENT   As Long = 8    ' H  N entrega
Private Const C_CAM   As Long = 9    ' I  N camion
Private Const C_VEH   As Long = 10   ' J  Tipo camion
Private Const C_GRP   As Long = 11   ' K  N grupo
Private Const C_CITA  As Long = 12   ' L  Referencia grupo = N cita
Private Const C_FEC   As Long = 13   ' M  Fecha cita
Private Const C_HORA  As Long = 14   ' N  Hora cita

Public Sub TrazWeb_Exportar(ByVal evento As String, Optional ByVal gruposSapOk As Object = Nothing)
    On Error GoTo fin
    Dim wsIn As Worksheet: Set wsIn = ThisWorkbook.Sheets(SH_IN)

    ' E2 trae "MDA", "MDA PREDISTRIBUIDO", "SDA STOCK" o "SDA PREDISTRIBUIDO":
    ' la primera palabra es la unidad de negocio y el resto la modalidad.
    Dim tipoPed As String: tipoPed = UCase$(Trim$(CStr(wsIn.Range("E2").Value)))
    Dim un As String: un = Split(tipoPed & " ", " ")(0)
    Dim modalidad As String
    If InStr(tipoPed, "PREDIS") > 0 Then modalidad = "Predistribuido" Else modalidad = "Stock"

    Dim js As String
    js = "{""tipo"":""od-traz"",""v"":1" & _
         ",""evento"":" & J(evento) & _
         ",""at"":" & J(Format$(Now, "yyyy-mm-dd hh:nn:ss")) & _
         ",""analista"":" & J(Analista()) & _
         ",""cliente"":" & J(UCase$(Trim$(CStr(wsIn.Range("D2").Value)))) & _
         ",""un"":" & J(un) & _
         ",""modalidad"":" & J(modalidad) & _
         ",""pedidos"":[" & PedidosJson() & "]" & _
         ",""entregas"":[" & EntregasJson(wsIn) & "]" & _
         ",""sapOk"":[" & SapOkJson(gruposSapOk) & "]}"

    Dim ruta As String: ruta = GuardarArchivo(js, evento)
    Dim msg As String
    msg = "Trazabilidad: paquete '" & evento & "' "
    If EnviarApi(js) Then
        msg = msg & "enviado a la plataforma"
    ElseIf Portapapeles(js) Then
        msg = msg & "sin conexion: quedo copiado, pegalo en la web con Ctrl+V"
    Else
        msg = msg & "sin conexion y sin portapapeles: usa el archivo .json"
    End If
    If Len(ruta) > 0 Then msg = msg & "  |  " & ruta
    Application.StatusBar = msg
    Application.OnTime Now + TimeSerial(0, 0, 30), "TrazWeb_LimpiarStatus"
fin:
End Sub

Public Sub TrazWeb_LimpiarStatus()
    Application.StatusBar = False
End Sub

' ---------------------------------------------------------
' Pedidos: 02_Posiciones (mismo codigo de material que VL01N)
' ---------------------------------------------------------
Private Function PedidosJson() As String
    On Error GoTo fin
    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(SH_POS)

    Dim hRow As Long, r As Long, c As Long
    Dim cSku As Long, cDesc As Long, cPed As Long, cPen As Long, cEnE As Long
    For r = 1 To 10
        For c = 1 To 30
            Select Case LCase$(Trim$(CStr(ws.Cells(r, c).Value)))
                Case "sku": cSku = c: hRow = r
                Case "descripcion": cDesc = c
                Case "pedido2", "pedido": cPed = c
                Case "qty pendiente": cPen = c
                Case "qty en entrega": cEnE = c
            End Select
        Next c
        If hRow > 0 Then Exit For
    Next r
    If hRow = 0 Or cSku = 0 Or cPed = 0 Then Exit Function

    Dim dic As Object: Set dic = CreateObject("Scripting.Dictionary")
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, cSku).End(xlUp).Row
    For r = hRow + 1 To lastRow
        Dim sku As String: sku = Texto(ws.Cells(r, cSku).Value)
        Dim ped As String: ped = Texto(ws.Cells(r, cPed).Value)
        If Len(sku) = 0 Or Len(ped) = 0 Then GoTo sig

        Dim desc As String: desc = ""
        If cDesc > 0 Then desc = Texto(ws.Cells(r, cDesc).Value)
        If Left$(desc, Len(sku) + 1) = sku & " " Then desc = Mid$(desc, Len(sku) + 2)

        Dim pen As Long, ene As Long: pen = 0: ene = 0
        If cPen > 0 Then pen = Entero(ws.Cells(r, cPen).Value)
        If cEnE > 0 Then ene = Entero(ws.Cells(r, cEnE).Value)

        Dim lin As String
        lin = "{""sku"":" & J(sku) & ",""desc"":" & J(desc) & _
              ",""pendiente"":" & CStr(pen) & ",""enEntrega"":" & CStr(ene) & "}"
        If dic.Exists(ped) Then dic(ped) = dic(ped) & "," & lin Else dic.Add ped, lin
sig:
    Next r

    ' La OC todavia no viaja en el paquete: se completa a mano en la web
    ' hasta que la leamos desde la pantalla de VL01N.
    Dim k As Variant, out As String
    For Each k In dic.Keys
        If Len(out) > 0 Then out = out & ","
        out = out & "{""pedido"":" & J(CStr(k)) & ",""lineas"":[" & dic(k) & "]}"
    Next k
    PedidosJson = out
fin:
End Function

' ---------------------------------------------------------
' Entregas: 01_Entrada H:N + productos desde 03_PedidoCubicado
' ---------------------------------------------------------
Private Function EntregasJson(ByVal wsIn As Worksheet) As String
    On Error GoTo fin
    Dim pedA2 As String: pedA2 = Texto(wsIn.Range("A2").Value)
    Dim r As Long, out As String

    For r = FILA_INI To FILA_FIN
        Dim ent As String: ent = Texto(wsIn.Cells(r, C_ENT).Value)
        If Len(ent) = 0 Or UCase$(ent) = "ERROR" Then GoTo sig

        Dim grp As String: grp = Texto(wsIn.Cells(r, C_GRP).Value)
        If UCase$(grp) = "SIN GRUPO" Then grp = ""

        Dim cam As Long: cam = Entero(wsIn.Cells(r, C_CAM).Value)
        Dim ped As String, carga As String, lineas As String
        ped = "": carga = ""
        lineas = LineasEntrega(ent, cam, ped, carga)
        If Len(ped) = 0 Then ped = pedA2

        If Len(out) > 0 Then out = out & ","
        out = out & "{""entrega"":" & J(ent) & _
                    ",""pedido"":" & J(ped) & _
                    ",""camion"":" & CStr(cam) & _
                    ",""vehiculo"":" & J(Texto(wsIn.Cells(r, C_VEH).Value)) & _
                    ",""grupo"":" & J(grp) & _
                    ",""cita"":" & J(Texto(wsIn.Cells(r, C_CITA).Value)) & _
                    ",""fecha"":" & J(FechaISO(wsIn.Cells(r, C_FEC).Value)) & _
                    ",""hora"":" & J(HoraHM(wsIn.Cells(r, C_HORA).Value)) & _
                    ",""carga"":" & J(carga) & _
                    ",""lineas"":[" & lineas & "]}"
sig:
    Next r
    EntregasJson = out
fin:
End Function

' Productos de una entrega. Usa la columna "N Entrega" de 03 si existe;
' si no, cae al N de camion. Devuelve tambien pedido y tipo de carga
' (MONO/MIX segun cantidad de SKU distintos).
Private Function LineasEntrega(ByVal ent As String, ByVal cam As Long, _
                               ByRef ped As String, ByRef carga As String) As String
    On Error GoTo fin
    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(SH_CUB)

    Dim c As Long, h As String
    Dim cEnt As Long, cPed As Long
    For c = 1 To 25
        h = LCase$(Trim$(CStr(ws.Cells(1, c).Value)))
        If h = "n entrega" Or h = "n" & Chr(176) & " entrega" Or h = "entrega" Then cEnt = c
        If h = "n pedido" Or h = "n" & Chr(176) & " pedido" Then cPed = c
    Next c

    Dim dic As Object: Set dic = CreateObject("Scripting.Dictionary")
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    Dim r As Long
    For r = 2 To lastRow
        Dim esta As Boolean
        If cEnt > 0 Then
            esta = (Texto(ws.Cells(r, cEnt).Value) = ent)
        Else
            esta = (cam > 0 And Entero(ws.Cells(r, 1).Value) = cam)
        End If
        If Not esta Then GoTo sig

        Dim sku As String: sku = Texto(ws.Cells(r, 4).Value)   ' D Codigo SAP
        Dim q As Long: q = Entero(ws.Cells(r, 6).Value)        ' F Unidades
        If Len(sku) = 0 Or q <= 0 Then GoTo sig
        If dic.Exists(sku) Then dic(sku) = dic(sku) + q Else dic.Add sku, q

        If Len(ped) = 0 And cPed > 0 Then
            ped = Texto(ws.Cells(r, cPed).Value)
            If Left$(ped, 4) = "_row" Then ped = ""
        End If
sig:
    Next r

    ' Tipo de carga del camion: MONO = un solo producto, MIX = varios
    If dic.Count = 1 Then
        carga = "MONO"
    ElseIf dic.Count > 1 Then
        carga = "MIX"
    End If

    Dim k As Variant, out As String
    For Each k In dic.Keys
        If Len(out) > 0 Then out = out & ","
        out = out & "{""sku"":" & J(CStr(k)) & ",""qty"":" & CStr(dic(k)) & "}"
    Next k
    LineasEntrega = out
fin:
End Function

Private Function SapOkJson(ByVal d As Object) As String
    On Error GoTo fin
    If d Is Nothing Then Exit Function
    Dim k As Variant, out As String
    For Each k In d.Keys
        If Len(out) > 0 Then out = out & ","
        out = out & J(CStr(k))
    Next k
    SapOkJson = out
fin:
End Function

' ---------------------------------------------------------
' Utilidades
' ---------------------------------------------------------
Private Function Analista() As String
    Dim n As String: n = ThisWorkbook.Name
    If InStrRev(n, ".") > 0 Then n = Left$(n, InStrRev(n, ".") - 1)
    If InStr(n, "_") > 0 Then n = Split(n, "_")(0)
    Analista = Trim$(n)
End Function

Private Function Texto(ByVal v As Variant) As String
    If IsError(v) Or IsEmpty(v) Then Exit Function
    If IsNumeric(v) And VarType(v) <> vbString Then
        Texto = Format$(v, "0")
    Else
        Texto = Trim$(CStr(v))
    End If
End Function

' Enteros sin separador decimal (evita "11,5" por configuracion regional)
Private Function Entero(ByVal v As Variant) As Long
    If IsError(v) Or IsEmpty(v) Then Exit Function
    If IsNumeric(v) Then Entero = CLng(Round(CDbl(v), 0))
End Function

Private Function FechaISO(ByVal v As Variant) As String
    On Error GoTo fin
    If IsError(v) Or IsEmpty(v) Then Exit Function
    If VarType(v) = vbDate Or (IsNumeric(v) And VarType(v) <> vbString) Then
        FechaISO = Format$(CDate(v), "yyyy-mm-dd")
        Exit Function
    End If
    Dim s As String: s = Replace(Replace(Trim$(CStr(v)), "/", "."), "-", ".")
    Dim p() As String: p = Split(s, ".")
    If UBound(p) = 2 Then
        Dim y As Long: y = CLng(p(2)): If y < 100 Then y = y + 2000
        FechaISO = Format$(DateSerial(y, CLng(p(1)), CLng(p(0))), "yyyy-mm-dd")
    End If
fin:
End Function

Private Function HoraHM(ByVal v As Variant) As String
    On Error GoTo fin
    If IsError(v) Or IsEmpty(v) Then Exit Function
    If VarType(v) = vbDate Or (IsNumeric(v) And VarType(v) <> vbString) Then
        HoraHM = Format$(CDate(v), "hh:nn")
    Else
        Dim s As String: s = Trim$(CStr(v))
        If Len(s) >= 4 And InStr(s, ":") > 0 Then
            HoraHM = Right$("0" & Split(s, ":")(0), 2) & ":" & Left$(Split(s, ":")(1), 2)
        End If
    End If
fin:
End Function

Private Function J(ByVal s As String) As String
    Dim i As Long, ch As String, code As Long, out As String
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        code = AscW(ch)
        Select Case True
            Case ch = """": out = out & "\"""
            Case ch = "\": out = out & "\\"
            Case code = 10: out = out & "\n"
            Case code = 13: out = out & "\r"
            Case code = 9: out = out & "\t"
            Case code >= 0 And code < 32: out = out & " "
            Case code < 0 Or code > 126: out = out & "\u" & Right$("0000" & LCase$(Hex$(code And &HFFFF&)), 4)
            Case Else: out = out & ch
        End Select
    Next i
    J = """" & out & """"
End Function

' POST a la plataforma. Timeout corto para no frenar el flujo si no esta abierta.
Private Function EnviarApi(ByVal texto As String) As Boolean
    On Error GoTo fin
    Dim http As Object
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 2000, 2000, 5000, 15000
    http.Open "POST", API_URL, False
    http.setRequestHeader "Content-Type", "application/json"
    http.send texto
    EnviarApi = (http.Status = 200)
    If Not EnviarApi Then Debug.Print "TrazWeb API " & http.Status & ": " & Left$(http.responseText, 300)
fin:
End Function

Private Function Portapapeles(ByVal texto As String) As Boolean
    On Error GoTo errClip
    Dim obj As Object
    Set obj = CreateObject("new:{1C3B4210-F441-11CE-B9EA-00AA006B1A69}")
    obj.SetText texto
    obj.PutInClipboard
    Portapapeles = True
    Exit Function
errClip:
    Portapapeles = False
End Function

Private Function GuardarArchivo(ByVal texto As String, ByVal evento As String) As String
    On Error GoTo fin
    Dim dirPath As String: dirPath = ThisWorkbook.Path & "\" & CARPETA
    If Len(Dir$(dirPath, vbDirectory)) = 0 Then MkDir dirPath
    Dim f As String
    f = dirPath & "\od_" & evento & "_" & Format$(Now, "yyyymmdd_hhnnss") & ".json"
    Dim n As Integer: n = FreeFile
    Open f For Output As #n
    Print #n, texto;          ' ASCII puro: J() ya escapa acentos como \uXXXX
    Close #n
    GuardarArchivo = f
fin:
End Function
