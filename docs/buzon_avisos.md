# Buzón de avisos de la cola (#291, 14-11)

Esta rama existe solo para el pull request «buzón»: **nunca se fusiona**. La cola de la nube (flujo «Cola», GitHub
Actions) comenta en ese PR únicamente cuando algo necesita a Claude (un trabajo que acaba, falla o queda en «revisar»,
o un lanzamiento que Kaggle rechaza). La sesión de Claude está suscrita a la actividad del PR, así que despierta en
ese momento: sin sondeos y sin gastar nada mientras no pasa nada. El estado completo sigue en la rama `nube-logs`.
