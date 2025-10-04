// script.js - Versão organizada para múltiplas páginas

// Funções gerais
const setupModals = () => {
    // Configura todos os modais da página
    document.querySelectorAll('[data-modal]').forEach(btn => {
        const modalId = btn.getAttribute('data-modal');
        const modal = document.getElementById(modalId);
        
        if(modal) {
            btn.onclick = () => modal.style.display = 'block';
            
            // Fechar modal
            modal.querySelectorAll('[data-close]').forEach(closeBtn => {
                closeBtn.onclick = () => modal.style.display = 'none';
            });
            
            // Fechar ao clicar fora
            modal.onclick = (e) => {
                if(e.target === modal) modal.style.display = 'none';
            };
        }
    });
};

// Página específica - students.html
const setupStudentsPage = () => {
    const turma = document.body.getAttribute('data-turma');
    if(!turma) return;

    // Filtro de pesquisa
    const searchInput = document.getElementById('searchInput');
    if(searchInput) {
        searchInput.addEventListener('input', () => {
            const termo = searchInput.value.toLowerCase();
            document.querySelectorAll('#studentsTable tbody tr').forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(termo) ? '' : 'none';
            });
        });
    }

    // Adicionar aluno
    const addForm = document.getElementById('addStudentForm');
    if(addForm) {
        addForm.onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(addForm);
            
            try {
                const response = await fetch(`/api/aluno/${turma}`, {
                    method: 'POST',
                    body: JSON.stringify({
                        nome: formData.get('nome'),
                        chamada: formData.get('chamada')
                    }),
                    headers: {'Content-Type': 'application/json'}
                });
                
                const result = await response.json();
                if(result.success) location.reload();
                else alert(result.error);
            } catch (error) {
                alert('Erro na conexão');
            }
        };
    }

    // Importar CSV
    const importForm = document.getElementById('importCSVForm');
    if(importForm) {
        importForm.onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(importForm);
            
            try {
                const response = await fetch(`/api/turma/${turma}/importar`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                if(result.success) location.reload();
                else alert(result.error);
            } catch (error) {
                alert('Erro na importação');
            }
        };
    }
};

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    setupModals();
    
    // Detecta qual página está carregada
    if(document.querySelector('#studentsTable')) {
        setupStudentsPage();
    }   
});