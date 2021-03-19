package com.apress.todo.repository;

import com.apress.todo.domain.ToDo;

import java.util.Collection;

public interface  CommonRepository<T> {
    public T save(T domain);
    public Iterable<T> save(Collection<T> domains);
    public void delete(T domain);
    public T findById(String id);
    public Iterable<T> findAll();
}
