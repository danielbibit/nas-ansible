# Rsync manual

## copy
Copia o conteudo de Library para Library
* Observar o / no final do origin

```sh
sudo rsync -a --info=progress2 --remove-source-files /path/origin/ /path/destination
```
