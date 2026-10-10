# Solución para la SIM en el MitraStar de Movistar

Probado en **IGW-1121GX2X2-Mv3**, hardware 1.0, firmware
`GL_g1.0_100AVK0_b2`. La SIM funcionaba en el móvil, pero el router no conseguía
conectarse. Se recuperó internet sin cambiar el firmware: primero con una SIM
de O2 España en Movistar 5G SA y después con otra SIM en 5G NSA.

## Qué fallaba

- En este firmware, la pantalla web de PIN acaba llamando a la recuperación
  por PUK en lugar de verificar el PIN normalmente. No insistas en esa pantalla.
- **La protección por PIN debe estar activada.** Una SIM puede tener un PIN
  asignado y no pedirlo al arrancar. El firmware pone esas tarjetas en estado
  de bloqueo interno. Activa la protección en un móvil usando el PIN correcto.
- La automatización reconoce una SIM concreta por su ICCID. **Cambiar de SIM
  exige volver a registrarla**, aunque tenga el mismo PIN.

El aviso de bloqueo por domicilio desapareció en nuestras pruebas al
inicializar correctamente la SIM. Esto no demuestra que todos los bloqueos de
operador o contrato se puedan resolver con este método.

## Instalación

1. Comprueba que la SIM funciona en un móvil y que la protección por PIN está
   activada. Confirma el PIN; no lo adivines. Para O2 España se probó el APN
   `telefonica.es`, autenticación PAP y usuario/contraseña `telefonica`.
2. Conecta el ordenador al router por Ethernet. Conserva una conexión Wi-Fi o
   hotspot independiente si necesitas seguir teniendo internet durante las pruebas.
3. En el equipo probado, SSH era `1234@192.168.8.1` con la contraseña web de la
   pegatina, y esa cuenta tenía permisos de root. Verifica la identidad del
   servidor; otra versión de firmware puede tener accesos distintos.
4. Ejecuta en tu **ordenador**:

   ```sh
   git clone https://github.com/BielC/mitrastar-igw1121-sim-pin-fix.git
   cd mitrastar-igw1121-sim-pin-fix
   tar -C router -cf - install.sh sim-pin-unlock enroll-sim-pin zzz_sim_pin_unlock |
     ssh 1234@192.168.8.1 'umask 077; mkdir /tmp/igw1121-pin-fix && tar -xf - -C /tmp/igw1121-pin-fix'
   ssh -t 1234@192.168.8.1 '/bin/sh /tmp/igw1121-pin-fix/install.sh'
   ```

   El instalador pide el PIN dos veces sin mostrarlo. Lee el ICCID localmente y
   guarda ambos en archivos accesibles solo por root. Registrar el PIN **no
   verifica que sea correcto**: introduce únicamente el PIN ya confirmado en
   el móvil. El instalador no envía un PIN, no cambia ajustes del módem ni reinicia nada.
5. Si la SIM está esperando el PIN, dentro de SSH puedes ejecutar una vez:

   ```sh
   /usr/sbin/sim-pin-unlock
   cat /tmp/sim-pin-unlock/status
   ```

6. Cuando puedas tolerar el corte, reinicia el router una vez con una conexión
   alternativa disponible. Después comprueba:

   ```sh
   cat /tmp/sim-pin-unlock/status
   mipc_wan_cli --show_sim_status
   mipc_wan_cli --show_register_status
   cmctl get apnInfo 1
   ```

`PIN accepted; SIM is ready.` confirma el desbloqueo. `apnConnStatus: 1` confirma
una sesión de datos, que puede tardar algo más. Verifica también acceso a
internet: aceptar el PIN por sí solo no demuestra que exista conexión.

La automatización se probó en un reinicio real del router. El instalador y la
herramienta pública de registro son nuevos y tienen pruebas aisladas con un
módem simulado; no se han instalado en un segundo router físico.

## Cambiar la SIM

Activa la protección y confirma el PIN de la nueva tarjeta en un móvil. Con
ella insertada, ejecuta desde el ordenador:

```sh
ssh -t 1234@192.168.8.1 /usr/sbin/enroll-sim-pin
```

El registro no envía el PIN ni borra la marca de intento de este arranque.
Reinicia una vez cuando sea conveniente para inicializar el módem con esa SIM.
La herramienta guarda una copia privada del registro anterior.

## Seguridad y límites

Solo se permite un intento por arranque y únicamente si coincide la SIM.
Un fallo o una interrupción bloquean nuevos intentos, incluso después de
reiniciar, hasta que se revise. No se envía PUK ni se cambia el firmware, el
APN, la protección por PIN o la red desde el servicio automático.

El PIN queda en texto plano en el router, protegido por permisos de root.
Procesos privilegiados y logs del fabricante pueden revelar datos privados.
No publiques PIN, PUK, ICCID, IMSI, IMEI, contraseñas, backups XML ni logs sin
revisarlos. El repositorio no contiene datos reales de la tarjeta ni del router.

Para desactivarlo, dentro de SSH:

```sh
/etc/init.d/zzz_sim_pin_unlock disable
/etc/init.d/zzz_sim_pin_unlock stop
```

Consulta [diagnóstico y eliminación](troubleshooting.md) y
[hallazgos técnicos](findings.md). Otros modelos o versiones no están probados;
no uses firmware del GX4X4 en el GX2X2 para seguir esta guía.
