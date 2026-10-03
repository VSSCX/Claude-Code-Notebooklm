Attribute VB_Name = "TrazWebAcciones"
Option Explicit

' =========================================================
' TrazWebAcciones.bas - Acciones que la plataforma ejecuta
'
' Cada funcion devuelve una cadena de estado que la plataforma muestra:
'   "OK ..."     termino bien
'   "ERROR ..."  no se ejecuto (la plataforma lo marca en rojo)
'
' Ninguna de estas funciones borra ni modifica nada en SAP,
' salvo TrazWeb_EliminarEntregaSAP, que viene SIN implementar a proposito.
' =========================================================

Private Const SH_IN As String = "01_Entrada"

' --- Actualizar bases (plan de ventas y saldos) -----------
Public Function TrazWeb_ActualizarBases() As String
    On Error GoTo fallo
    ThisWorkbook.RefrescarTodo
    TrazWeb_ActualizarBases = "OK bases actualizadas"
    Exit Function
fallo:
    TrazWeb_ActualizarBases = "ERROR al actualizar bases: " & Err.Description
End Function

' --- Cubicaje --------------------------------------------
Public Function TrazWeb_Cubicar() As String
    On Error GoTo fallo
    If Len(Texto(Hoja(SH_IN).Range("A2").Value)) = 0 Then
        TrazWeb_Cubicar = "ERROR no hay pedido cargado en 01_Entrada"
        Exit Function
    End If
    SegmentarEnCamiones
    TrazWeb_Cubicar = "OK cubicaje ejecutado"
    Exit Function
fallo:
    TrazWeb_Cubicar = "ERROR al cubicar: " & Err.Description
End Function

Public Function TrazWeb_Simular() As String
    On Error GoTo fallo
    SimularCubicaje
    TrazWeb_Simular = "OK simulacion ejecutada"
    Exit Function
fallo:
    TrazWeb_Simular = "ERROR al simular: " & Err.Description
End Function

' --- Visor 3D: devuelve la ruta del HTML generado ---------
Public Function TrazWeb_Visor(Optional ByVal pedido As String = "") As String
    On Error GoTo fallo
    Dim ruta As String
    ruta = GenerarVisorArchivo()
    If Len(ruta) = 0 Then
        TrazWeb_Visor = "ERROR no hay cubicaje para visualizar o falta la plantilla"
    Else
        TrazWeb_Visor = ruta          ' la plataforma guarda una copia
    End If
    Exit Function
fallo:
    TrazWeb_Visor = "ERROR al generar el visor: " & Err.Description
End Function

' --- Flujo SAP -------------------------------------------
' Escribe el pedido en 01_Entrada y extrae el picking.
' Se niega a pisar un pedido distinto que ya este cargado.
Public Function TrazWeb_LeerPedido(ByVal pedido As String) As String
    On Error GoTo fallo
    Dim ws As Worksheet: Set ws = Hoja(SH_IN)
    Dim actual As String: actual = Texto(ws.Range("A2").Value)
    If Len(actual) > 0 And actual <> Trim$(pedido) Then
        TrazWeb_LeerPedido = "ERROR el libro tiene cargado el pedido " & actual & _
                             ". Limpia el proceso antes de leer otro."
        Exit Function
    End If
    ws.Range("A2").Value = Trim$(pedido)
    Extraer_Picking_NAVBTN
    TrazWeb_LeerPedido = "OK pedido " & Trim$(pedido) & " leido"
    Exit Function
fallo:
    TrazWeb_LeerPedido = "ERROR al leer el pedido: " & Err.Description
End Function

Public Function TrazWeb_CrearEntregas() As String
    On Error GoTo fallo
    VL01N_CrearEntregas_TodosLosCamiones
    TrazWeb_CrearEntregas = "OK entregas creadas"
    Exit Function
fallo:
    TrazWeb_CrearEntregas = "ERROR al crear entregas: " & Err.Description
End Function

Public Function TrazWeb_CrearGrupos() As String
    On Error GoTo fallo
    CrearGruposTransporte
    TrazWeb_CrearGrupos = "OK grupos creados"
    Exit Function
fallo:
    TrazWeb_CrearGrupos = "ERROR al crear grupos: " & Err.Description
End Function

Public Function TrazWeb_Limpiar() As String
    On Error GoTo fallo
    LimpiarProceso
    TrazWeb_Limpiar = "OK proceso limpiado"
    Exit Function
fallo:
    TrazWeb_Limpiar = "ERROR al limpiar: " & Err.Description
End Function

' =========================================================
' BORRADO EN SAP - SIN IMPLEMENTAR A PROPOSITO
'
' Para completarla hay que grabar en SAP (Mas > Grabar y reproducir)
' la secuencia real de VL02N: abrir la entrega, verificar que NO tenga
' salida de mercancia, NO este facturada y NO pertenezca a un grupo,
' y recien ahi borrar. Si alguna verificacion falla, devolver
' "ERROR <motivo>" y NO borrar: la plataforma conserva la entrega.
'
' Mientras devuelva ERROR, la plataforma nunca borra nada en SAP.
' =========================================================
Public Function TrazWeb_EliminarEntregaSAP(ByVal entrega As String) As String
    TrazWeb_EliminarEntregaSAP = "ERROR el borrado en SAP todavia no esta implementado " & _
                                 "(entrega " & Trim$(entrega) & ")"
End Function

' --- Utilidades ------------------------------------------
Private Function Hoja(ByVal nombre As String) As Worksheet
    Set Hoja = ThisWorkbook.Sheets(nombre)
End Function

Private Function Texto(ByVal v As Variant) As String
    If IsError(v) Or IsEmpty(v) Then Exit Function
    If IsNumeric(v) And VarType(v) <> vbString Then
        Texto = Format$(v, "0")
    Else
        Texto = Trim$(CStr(v))
    End If
End Function
