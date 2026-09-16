with open('templates/cadastros/confirm_delete_base.html', 'r') as f:
    content = f.read()

# Add auto-check checkbox logic before </script>
content = content.replace(
    'console.log(\'Run testDeleteSubmit() in console to test form submission manually\');\n\n// ALERT ON CLICK',
    'console.log(\'Run testDeleteSubmit() in console to test form submission manually\');\n\n// AUTO-CHECK CHECKBOX ON PAGE LOAD\nwindow.addEventListener(\'DOMContentLoaded\', function() {\n    var checkbox = document.getElementById(\'id_delete_apontamentos\');\n    if (checkbox && !checkbox.checked) {\n        console.log(\'Auto-checking delete_apontamentos checkbox\');\n        checkbox.checked = true;\n    }\n});\n\n// ALERT ON CLICK'
)

with open('templates/cadastros/confirm_delete_base.html', 'w') as f:
    f.write(content)
print('Fixed')